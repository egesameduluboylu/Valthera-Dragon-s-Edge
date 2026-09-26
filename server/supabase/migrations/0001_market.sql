-- Valthera: Dragon's Edge - player marketplace (docs/13-pazar.md).
--
-- Players sign in anonymously (Supabase Auth). Clients never write the tables
-- directly: row level security only lets them read, and every change goes through
-- the security-definer functions below, which check the item against the game's
-- item rules (market_config, seeded from data/*.json by tools/market/seed_catalog.py).

create table if not exists public.market_config (
  key   text primary key,
  value jsonb not null
);

create table if not exists public.players (
  id         uuid primary key references auth.users (id) on delete cascade,
  name       text not null check (char_length(name) between 3 and 24),
  created_at timestamptz not null default now()
);

create table if not exists public.listings (
  id          uuid primary key default gen_random_uuid(),
  seller      uuid not null references public.players (id) on delete cascade,
  seller_name text not null,
  -- The seller's own id for the item (save id + bag uid): an item can be listed only once.
  item_uid    text not null check (char_length(item_uid) between 1 and 80),
  item        jsonb not null,
  slot        text not null,
  rarity      text not null,
  is_unique   boolean not null default false,
  price       integer not null check (price > 0),
  status      text not null default 'active' check (status in ('active', 'sold', 'cancelled', 'expired')),
  buyer       uuid references public.players (id) on delete set null,
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null,
  closed_at   timestamptz
);
create index if not exists listings_browse on public.listings (status, slot, rarity, price);
create index if not exists listings_seller on public.listings (seller, status);
create unique index if not exists listings_seller_item on public.listings (seller, item_uid);
create index if not exists listings_buyer on public.listings (buyer, closed_at);

-- Gold from sales and items that came back, waiting for their owner to collect them.
create table if not exists public.mailbox (
  id         uuid primary key default gen_random_uuid(),
  owner      uuid not null references public.players (id) on delete cascade,
  kind       text not null check (kind in ('gold', 'item')),
  gold       integer not null default 0,
  item       jsonb,
  note       text not null,
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  -- Claim receipt: the client's operation id. A retry with the same id (after a lost
  -- response) gets the same reward back instead of an error.
  claim_op   text
);
create index if not exists mailbox_owner on public.mailbox (owner, claimed_at);

alter table public.market_config enable row level security;
alter table public.players enable row level security;
alter table public.listings enable row level security;
alter table public.mailbox enable row level security;

drop policy if exists "read config" on public.market_config;
create policy "read config" on public.market_config for select to authenticated using (true);
drop policy if exists "read players" on public.players;
create policy "read players" on public.players for select to authenticated using (true);
drop policy if exists "read active or own listings" on public.listings;
create policy "read active or own listings" on public.listings for select to authenticated
  using (status = 'active' or seller = auth.uid());
drop policy if exists "read own mail" on public.mailbox;
create policy "read own mail" on public.mailbox for select to authenticated using (owner = auth.uid());

-- ---------------------------------------------------------------- helpers

create or replace function public._cfg(p_key text) returns jsonb
language sql stable security definer set search_path = public as $$
  select value from public.market_config where key = p_key
$$;

create or replace function public._fail(p_error text) returns jsonb
language sql immutable as $$ select jsonb_build_object('ok', false, 'error', p_error) $$;

-- Rounds like Godot's roundi (half away from zero).
create or replace function public._round(v numeric) returns integer
language sql immutable as $$ select (sign(v) * floor(abs(v) + 0.5))::integer $$;

-- Mirrors Items.shop_price: 4 * salvage gold.
create or replace function public._salvage_gold(p_item jsonb) returns integer
language plpgsql stable security definer set search_path = public as $$
declare
  v_order jsonb := public._cfg('items')->'rarity_order';
  v_tier integer := 0;
  i integer;
begin
  for i in 0 .. jsonb_array_length(v_order) - 1 loop
    if v_order->>i = p_item->>'rarity' then v_tier := i; end if;
  end loop;
  return 6 * (p_item->>'level')::integer * (v_tier + 1) + 10 * coalesce((p_item->>'upgrade')::integer, 0);
end $$;

-- Checks an item against the game's rules so edited saves can't sell impossible items.
-- Returns '' when the item is valid, else an error key.
create or replace function public.validate_item(p_item jsonb) returns text
language plpgsql stable security definer set search_path = public as $$
declare
  v_items jsonb := public._cfg('items');
  v_base jsonb;
  v_rarity jsonb;
  v_affix jsonb;
  v_def jsonb;
  v_level integer;
  v_upgrade integer;
  v_lo numeric;
  v_hi numeric;
  v_ids text[] := '{}';
  v_max_level integer := coalesce((public._cfg('market')->>'max_item_level')::integer, 20);
begin
  if jsonb_typeof(p_item) is distinct from 'object' then return 'market.err_bad_item'; end if;
  v_base := v_items->'bases'->(p_item->>'base');
  v_rarity := v_items->'rarities'->(p_item->>'rarity');
  if v_base is null or v_rarity is null then return 'market.err_bad_item'; end if;
  if v_base ? 'rarity' and v_base->>'rarity' <> p_item->>'rarity' then return 'market.err_bad_item'; end if;
  if (v_rarity->>'boss_only')::boolean is true and not (v_base ? 'unique') then
    null; -- legendary rolls exist from bosses; allowed
  end if;
  begin
    v_level := (p_item->>'level')::integer;
    v_upgrade := coalesce((p_item->>'upgrade')::integer, 0);
  exception when others then
    return 'market.err_bad_item';
  end;
  if v_level is null or v_level < 1 or v_level > v_max_level then return 'market.err_bad_item'; end if;
  if v_upgrade < 0 or v_upgrade > (v_items->>'max_upgrade')::integer then return 'market.err_bad_item'; end if;
  if jsonb_typeof(p_item->'affixes') is distinct from 'array' then return 'market.err_bad_item'; end if;
  if jsonb_array_length(p_item->'affixes') <> (v_rarity->>'affixes')::integer then return 'market.err_bad_item'; end if;
  for v_affix in select * from jsonb_array_elements(p_item->'affixes') loop
    -- every affix is {id: text, value: number}; JSON numbers are always finite
    if jsonb_typeof(v_affix) is distinct from 'object' or jsonb_typeof(v_affix->'id') is distinct from 'string'
        or jsonb_typeof(v_affix->'value') is distinct from 'number' then
      return 'market.err_bad_item';
    end if;
    v_def := v_items->'affixes'->(v_affix->>'id');
    if v_def is null or (v_affix->>'id') = any(v_ids) then return 'market.err_bad_item'; end if;
    v_ids := v_ids || (v_affix->>'id');
    v_lo := (v_def->'range'->>0)::numeric;
    v_hi := (v_def->'range'->>1)::numeric;
    if (v_def->>'scales')::boolean is true then
      v_lo := v_lo * (1 + (v_items->>'level_growth')::numeric * v_level);
      v_hi := v_hi * (1 + (v_items->>'level_growth')::numeric * v_level);
    end if;
    -- a little slack for rounding (whole-number stats round to the nearest int, min 1)
    if (v_affix->>'value')::numeric < least(v_lo, 1) - 0.51 or (v_affix->>'value')::numeric > v_hi + 0.51 then
      return 'market.err_bad_item';
    end if;
  end loop;
  return '';
end $$;

-- Serializes one player's market writes (listing and buying limits are count-then-insert).
create or replace function public._lock_player(p_player uuid) returns void
language sql volatile as $$ select pg_advisory_xact_lock(hashtext('market:' || p_player::text)) $$;

-- Closes the caller's listings that ran out of time and mails the items back.
create or replace function public._expire_for(p_player uuid) returns void
language plpgsql security definer set search_path = public as $$
declare r record;
begin
  for r in update public.listings set status = 'expired', closed_at = now()
      where seller = p_player and status = 'active' and expires_at <= now()
      returning item loop
    insert into public.mailbox (owner, kind, item, note) values (p_player, 'item', r.item, 'market.mail_expired');
  end loop;
end $$;

create or replace function public._listing_json(l public.listings) returns jsonb
language sql stable as $$
  select jsonb_build_object('id', l.id, 'seller', l.seller_name, 'item', l.item, 'price', l.price,
    'mine', l.seller = auth.uid(), 'expires_at', l.expires_at, 'status', l.status)
$$;

-- ---------------------------------------------------------------- API (called via /rest/v1/rpc)

-- Creates or renames the caller's market profile.
create or replace function public.market_join(p_name text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_name text := btrim(coalesce(p_name, ''));
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  if char_length(v_name) < 3 or char_length(v_name) > 24 then return public._fail('market.err_name'); end if;
  insert into public.players (id, name) values (auth.uid(), v_name)
    on conflict (id) do update set name = excluded.name;
  return jsonb_build_object('ok', true);
end $$;

create or replace function public.market_browse(p_slot text default '', p_rarity text default '',
    p_unique boolean default false, p_sort text default 'price', p_limit integer default 40, p_offset integer default 0)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare v jsonb;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  select coalesce(jsonb_agg(public._listing_json(l) order by
      case when p_sort = 'price' then l.price end asc,
      case when p_sort = 'price_desc' then l.price end desc,
      l.created_at desc), '[]'::jsonb)
    into v
    from (select * from public.listings
          where status = 'active' and expires_at > now()
            and (coalesce(p_slot, '') = '' or slot = p_slot)
            and (coalesce(p_rarity, '') = '' or rarity = p_rarity)
            and (not coalesce(p_unique, false) or is_unique)
          order by
            case when p_sort = 'price' then price end asc,
            case when p_sort = 'price_desc' then price end desc,
            created_at desc
          limit least(greatest(coalesce(p_limit, 40), 1), 100) offset greatest(coalesce(p_offset, 0), 0)) l;
  return jsonb_build_object('ok', true, 'listings', v);
end $$;

create or replace function public.market_my_listings() returns jsonb
language plpgsql security definer set search_path = public as $$
declare v jsonb;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  perform public._expire_for(auth.uid());
  select coalesce(jsonb_agg(public._listing_json(l) order by l.created_at), '[]'::jsonb) into v
    from public.listings l where l.seller = auth.uid() and l.status = 'active';
  return jsonb_build_object('ok', true, 'listings', v);
end $$;

-- The client removes the item from its bag and pays the listing fee after an ok.
-- p_item carries the seller's item uid; an item uid is accepted once per seller, and a
-- retry of the same listing (lost response) gets the same listing back.
create or replace function public.market_create_listing(p_item jsonb, p_price integer) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_market jsonb := public._cfg('market');
  v_items jsonb := public._cfg('items');
  v_player public.players;
  v_uid text := p_item->>'uid';
  v_item jsonb := p_item - 'uid';
  v_err text;
  v_min integer;
  v_active integer;
  v_today integer;
  v_listing public.listings;
  v_fee integer;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  select * into v_player from public.players where id = auth.uid();
  if not found then return public._fail('market.err_no_profile'); end if;
  v_err := public.validate_item(v_item);
  if v_err <> '' then return public._fail(v_err); end if;
  if jsonb_typeof(p_item->'uid') is distinct from 'string' or char_length(v_uid) not between 1 and 80 then
    return public._fail('market.err_bad_item');
  end if;
  v_min := greatest(1, public._salvage_gold(v_item));
  if p_price is null or p_price < v_min then return public._fail('market.err_price_low'); end if;
  if p_price > (v_market->>'max_price')::integer then return public._fail('market.err_price_high'); end if;
  v_fee := greatest((v_market->>'min_listing_fee')::integer,
                    public._round(p_price * (v_market->>'listing_fee_percent')::numeric));
  perform public._lock_player(auth.uid());
  select * into v_listing from public.listings where seller = auth.uid() and item_uid = v_uid;
  if found then
    if v_listing.status = 'active' and v_listing.item = v_item and v_listing.price = p_price then
      return jsonb_build_object('ok', true, 'listing', public._listing_json(v_listing), 'fee', v_fee);
    end if;
    return public._fail('market.err_listed_before');
  end if;
  perform public._expire_for(auth.uid());
  select count(*) into v_active from public.listings where seller = auth.uid() and status = 'active';
  if v_active >= (v_market->>'max_listings')::integer then return public._fail('market.err_too_many'); end if;
  select count(*) into v_today from public.listings
    where seller = auth.uid() and created_at > now() - interval '24 hours';
  if v_today >= (v_market->>'max_listings_per_day')::integer then return public._fail('market.err_daily_limit'); end if;
  insert into public.listings (seller, seller_name, item_uid, item, slot, rarity, is_unique, price, expires_at)
    values (auth.uid(), v_player.name, v_uid, v_item, v_items->'bases'->(v_item->>'base')->>'slot', v_item->>'rarity',
            (v_items->'bases'->(v_item->>'base')) ? 'unique', p_price,
            now() + make_interval(hours => (v_market->>'listing_hours')::integer))
    returning * into v_listing;
  return jsonb_build_object('ok', true, 'listing', public._listing_json(v_listing), 'fee', v_fee);
end $$;

create or replace function public.market_cancel_listing(p_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_item jsonb;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  update public.listings set status = 'cancelled', closed_at = now()
    where id = p_id and seller = auth.uid() and status = 'active'
    returning item into v_item;
  if v_item is null then return public._fail('market.err_gone'); end if;
  insert into public.mailbox (owner, kind, item, note) values (auth.uid(), 'item', v_item, 'market.mail_cancelled');
  return jsonb_build_object('ok', true);
end $$;

-- Marks the listing sold (only one buyer can win) and mails the seller the gold minus tax.
-- The client pays the price from its own gold and adds the returned item to its bag.
-- Gold lives in the client's save, so the server caps what one player can buy a day.
create or replace function public.market_buy(p_id uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_market jsonb := public._cfg('market');
  v_listing public.listings;
  v_tax numeric := (v_market->>'tax_percent')::numeric;
  v_count integer;
  v_gold bigint;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  if not exists (select 1 from public.players where id = auth.uid()) then return public._fail('market.err_no_profile'); end if;
  perform public._lock_player(auth.uid());
  select * into v_listing from public.listings where id = p_id;
  if not found then return public._fail('market.err_gone'); end if;
  if v_listing.seller = auth.uid() then return public._fail('market.err_own'); end if;
  select count(*), coalesce(sum(price), 0) into v_count, v_gold from public.listings
    where buyer = auth.uid() and status = 'sold' and closed_at > now() - interval '24 hours';
  if v_count >= (v_market->>'max_buys_per_day')::integer
      or v_gold + v_listing.price > (v_market->>'max_buy_gold_per_day')::bigint then
    return public._fail('market.err_buy_limit');
  end if;
  update public.listings set status = 'sold', buyer = auth.uid(), closed_at = now()
    where id = p_id and status = 'active' and expires_at > now() and seller <> auth.uid()
    returning * into v_listing;
  if not found then return public._fail('market.err_gone'); end if;
  insert into public.mailbox (owner, kind, gold, item, note)
    values (v_listing.seller, 'gold', v_listing.price - public._round(v_listing.price * v_tax), v_listing.item, 'market.mail_sold');
  return jsonb_build_object('ok', true, 'item', v_listing.item, 'price', v_listing.price);
end $$;

create or replace function public.market_mailbox() returns jsonb
language plpgsql security definer set search_path = public as $$
declare v jsonb;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  perform public._expire_for(auth.uid());
  select coalesce(jsonb_agg(jsonb_build_object('id', m.id, 'kind', m.kind, 'gold', m.gold, 'item', m.item,
      'note', m.note) order by m.created_at), '[]'::jsonb)
    into v from public.mailbox m where m.owner = auth.uid() and m.claimed_at is null;
  return jsonb_build_object('ok', true, 'entries', v);
end $$;

-- Marks a mailbox entry collected and returns it; the client adds the gold or item.
-- p_op is the client's id for this claim, saved on its side before calling: asking again
-- with the same id returns the same reward, so a lost response loses nothing.
drop function if exists public.market_claim(uuid);
create or replace function public.market_claim(p_id uuid, p_op text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v public.mailbox;
begin
  if auth.uid() is null then return public._fail('market.err_auth'); end if;
  if p_op is null or char_length(p_op) not between 8 and 64 then return public._fail('market.err_bad_request'); end if;
  update public.mailbox set claimed_at = now(), claim_op = p_op
    where id = p_id and owner = auth.uid() and claimed_at is null
    returning * into v;
  if v.id is null then
    select * into v from public.mailbox where id = p_id and owner = auth.uid() and claim_op = p_op;
    if v.id is null then return public._fail('market.err_gone'); end if;
  end if;
  if v.kind = 'gold' then return jsonb_build_object('ok', true, 'gold', v.gold); end if;
  return jsonb_build_object('ok', true, 'item', v.item);
end $$;

-- Functions are executable by PUBLIC by default (and Supabase also grants anon). Only
-- signed-in players may use the market API; the helpers stay internal.
revoke all on function public._cfg(text), public._fail(text), public._round(numeric), public._salvage_gold(jsonb),
  public.validate_item(jsonb), public._lock_player(uuid), public._expire_for(uuid), public._listing_json(public.listings),
  public.market_join(text), public.market_browse(text, text, boolean, text, integer, integer),
  public.market_my_listings(), public.market_create_listing(jsonb, integer), public.market_cancel_listing(uuid),
  public.market_buy(uuid), public.market_mailbox(), public.market_claim(uuid, text)
  from public, anon, authenticated;
grant execute on function public.market_join(text), public.market_browse(text, text, boolean, text, integer, integer),
  public.market_my_listings(), public.market_create_listing(jsonb, integer), public.market_cancel_listing(uuid),
  public.market_buy(uuid), public.market_mailbox(), public.market_claim(uuid, text) to authenticated;
