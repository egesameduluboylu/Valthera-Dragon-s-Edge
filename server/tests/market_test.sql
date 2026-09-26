-- Runs the marketplace functions as two players and checks the results.
-- Any failed check raises an exception, so psql exits non-zero (ON_ERROR_STOP).
\set ON_ERROR_STOP on
-- Supabase grants table rights to these roles by default; row level security is what protects the tables.
grant all on all tables in schema public to anon, authenticated;

insert into auth.users values ('00000000-0000-0000-0000-00000000000a'), ('00000000-0000-0000-0000-00000000000b');

create or replace function pg_temp.as_player(p text) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claim.sub', p, false);
  execute 'set role authenticated';
end $$;

create or replace function pg_temp.check(cond boolean, msg text) returns void language plpgsql as $$
begin
  if not coalesce(cond, false) then raise exception 'CHECK FAILED: %', msg; end if;
end $$;

do $$
declare
  a text := '00000000-0000-0000-0000-00000000000a';
  b text := '00000000-0000-0000-0000-00000000000b';
  r jsonb;
  good jsonb := '{"uid": "i7", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 1,
                  "affixes": [{"id": "crit", "value": 0.02}]}';
  lid uuid;
  mail uuid;
  i integer;
begin
  -- player a joins and lists an item
  perform set_config('request.jwt.claim.sub', a, false);
  set local role authenticated;
  r := public.market_join('Kara Ayşe');
  perform pg_temp.check((r->>'ok')::boolean, 'join a ' || r::text);
  r := public.market_create_listing(good, 5);
  perform pg_temp.check(r->>'error' = 'market.err_no_profile' or r->>'error' = 'market.err_price_low', 'low price ' || r::text);
  r := public.market_create_listing(good, 300);
  perform pg_temp.check((r->>'ok')::boolean, 'create ' || r::text);
  perform pg_temp.check((r->>'fee')::int = 15, 'fee ' || r::text);
  perform pg_temp.check(not (r->'listing'->'item' ? 'uid'), 'uid stripped');
  lid := (r->'listing'->>'id')::uuid;
  -- a retry after a lost answer gets the same listing; the same item can't be listed twice
  r := public.market_create_listing(good, 300);
  perform pg_temp.check((r->>'ok')::boolean and (r->'listing'->>'id')::uuid = lid, 'retry ' || r::text);
  r := public.market_create_listing(good, 400);
  perform pg_temp.check(r->>'error' = 'market.err_listed_before', 'listed twice ' || r::text);
  r := public.market_create_listing(good - 'uid', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'no uid ' || r::text);

  -- impossible items are refused
  r := public.market_create_listing('{"base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": [{"id": "crit", "value": 0.9}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix too high ' || r::text);
  r := public.market_create_listing('{"base": "iron_helm", "rarity": "epic", "level": 2, "upgrade": 0, "affixes": [{"id": "crit", "value": 0.02}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'wrong affix count ' || r::text);
  r := public.market_create_listing('{"base": "bone_crown", "rarity": "common", "level": 3, "upgrade": 0, "affixes": []}', 900);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'unique with wrong rarity ' || r::text);
  r := public.market_create_listing('{"base": "sword_of_hax", "rarity": "common", "level": 3, "upgrade": 0, "affixes": []}', 900);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'unknown base ' || r::text);
  r := public.market_create_listing('{"base": "iron_helm", "rarity": "common", "level": 3, "upgrade": 99, "affixes": []}', 900);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'upgrade too high ' || r::text);
  -- affixes must be {id, value} with a number in range
  r := public.market_create_listing('{"uid": "x1", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": [{"id": "crit"}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix without value ' || r::text);
  r := public.market_create_listing('{"uid": "x2", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": [{"id": "crit", "value": "0.02"}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix value as text ' || r::text);
  r := public.market_create_listing('{"uid": "x3", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": [{"id": "crit", "value": null}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix value null ' || r::text);
  r := public.market_create_listing('{"uid": "x4", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": ["crit"]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix not an object ' || r::text);
  r := public.market_create_listing('{"uid": "x5", "base": "iron_helm", "rarity": "rare", "level": 2, "upgrade": 0, "affixes": [{"id": "crit", "value": -5}]}', 300);
  perform pg_temp.check(r->>'error' = 'market.err_bad_item', 'affix value too low ' || r::text);

  -- cannot buy your own
  r := public.market_buy(lid);
  perform pg_temp.check(r->>'error' = 'market.err_own', 'own ' || r::text);

  -- listing limit
  for i in 1 .. 4 loop
    r := public.market_create_listing(jsonb_build_object('uid', 'r' || i, 'base', 'copper_ring', 'rarity', 'common',
      'level', 1, 'upgrade', 0, 'affixes', '[]'::jsonb), 50);
    perform pg_temp.check((r->>'ok')::boolean, 'ring ' || r::text);
  end loop;
  r := public.market_create_listing('{"uid": "r5", "base": "copper_ring", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}', 50);
  perform pg_temp.check(r->>'error' = 'market.err_too_many', 'limit ' || r::text);
  r := public.market_my_listings();
  perform pg_temp.check(jsonb_array_length(r->'listings') = 5, 'my listings ' || r::text);

  -- player b browses and buys
  reset role;
  perform set_config('request.jwt.claim.sub', b, false);
  set local role authenticated;
  r := public.market_buy(lid);
  perform pg_temp.check(r->>'error' = 'market.err_no_profile', 'b needs a profile ' || r::text);
  perform public.market_join('Sessiz Mert');
  r := public.market_browse('helm', '', false, 'price', 40, 0);
  perform pg_temp.check(jsonb_array_length(r->'listings') = 1, 'browse helm ' || r::text);
  perform pg_temp.check((r->'listings'->0->>'mine')::boolean = false, 'not mine');
  r := public.market_browse('', '', false, 'price', 40, 0);
  perform pg_temp.check(jsonb_array_length(r->'listings') = 5, 'browse all ' || r::text);
  perform pg_temp.check((r->'listings'->0->>'price')::int <= (r->'listings'->4->>'price')::int, 'sorted');
  r := public.market_buy(lid);
  perform pg_temp.check((r->>'ok')::boolean and r->'item'->>'base' = 'iron_helm', 'buy ' || r::text);
  r := public.market_buy(lid);
  perform pg_temp.check(r->>'error' = 'market.err_gone', 'second buy ' || r::text);
  r := public.market_mailbox();
  perform pg_temp.check(jsonb_array_length(r->'entries') = 0, 'b has no mail');

  -- a collects 270 gold (300 - 10% tax), cancels a ring and gets it back
  reset role;
  perform set_config('request.jwt.claim.sub', a, false);
  set local role authenticated;
  r := public.market_mailbox();
  perform pg_temp.check(jsonb_array_length(r->'entries') = 1, 'a mail ' || r::text);
  mail := (r->'entries'->0->>'id')::uuid;
  r := public.market_claim(mail, 'short');
  perform pg_temp.check(r->>'error' = 'market.err_bad_request', 'claim needs an op id ' || r::text);
  r := public.market_claim(mail, 'op-a-0001');
  perform pg_temp.check((r->>'gold')::int = 270, 'claim gold ' || r::text);
  -- the answer got lost: the same op id gets the same reward, another op id gets nothing
  r := public.market_claim(mail, 'op-a-0001');
  perform pg_temp.check((r->>'gold')::int = 270, 'claim retry ' || r::text);
  r := public.market_claim(mail, 'op-a-0002');
  perform pg_temp.check(r->>'error' = 'market.err_gone', 'claim twice ' || r::text);
  r := public.market_mailbox();
  perform pg_temp.check(jsonb_array_length(r->'entries') = 0, 'claimed mail hidden ' || r::text);
  r := public.market_my_listings();
  r := public.market_cancel_listing((r->'listings'->0->>'id')::uuid);
  perform pg_temp.check((r->>'ok')::boolean, 'cancel ' || r::text);
  r := public.market_mailbox();
  perform pg_temp.check(r->'entries'->0->'item'->>'base' = 'copper_ring', 'ring back ' || r::text);
  mail := (r->'entries'->0->>'id')::uuid;

  -- someone else's mail can't be claimed, not even with the owner's op id
  reset role;
  perform set_config('request.jwt.claim.sub', b, false);
  set local role authenticated;
  r := public.market_claim(mail, 'op-a-0001');
  perform pg_temp.check(r->>'error' = 'market.err_gone', 'claim other mail ' || r::text);
  reset role;
  perform set_config('request.jwt.claim.sub', a, false);
  set local role authenticated;

  -- expired listings come back through the mailbox
  reset role;
  update public.listings set expires_at = now() - interval '1 minute' where seller = a::uuid and status = 'active';
  set local role authenticated;
  r := public.market_browse('', '', false, 'price', 40, 0);
  perform pg_temp.check(jsonb_array_length(r->'listings') = 0, 'expired hidden ' || r::text);
  r := public.market_mailbox();
  perform pg_temp.check(jsonb_array_length(r->'entries') = 4, 'expired mailed ' || r::text);

  -- a sold item can't be listed again (edited saves that keep a sold item)
  r := public.market_create_listing(good, 300);
  perform pg_temp.check(r->>'error' = 'market.err_listed_before', 'relist sold ' || r::text);

  -- daily caps: listings per seller, purchases (count and gold) per buyer
  reset role;
  update public.market_config set value = value || '{"max_listings_per_day": 7, "max_buys_per_day": 2,
    "max_buy_gold_per_day": 400}' where key = 'market';
  set local role authenticated;
  r := public.market_create_listing('{"uid": "d1", "base": "copper_ring", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}', 150);
  perform pg_temp.check((r->>'ok')::boolean, 'd1 ' || r::text);
  lid := (r->'listing'->>'id')::uuid;
  r := public.market_create_listing('{"uid": "d2", "base": "copper_ring", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}', 50);
  perform pg_temp.check((r->>'ok')::boolean, 'd2 ' || r::text);
  mail := (r->'listing'->>'id')::uuid;
  r := public.market_create_listing('{"uid": "d3", "base": "copper_ring", "rarity": "common", "level": 1, "upgrade": 0, "affixes": []}', 50);
  perform pg_temp.check(r->>'error' = 'market.err_daily_limit', 'daily listing cap ' || r::text);
  reset role;
  perform set_config('request.jwt.claim.sub', b, false);
  set local role authenticated;
  r := public.market_buy(lid);
  perform pg_temp.check(r->>'error' = 'market.err_buy_limit', 'daily gold cap (300 + 150 > 400) ' || r::text);
  r := public.market_buy(mail);
  perform pg_temp.check((r->>'ok')::boolean, 'buy under the caps ' || r::text);
  reset role;
  update public.market_config set value = value || '{"max_buy_gold_per_day": 200000}' where key = 'market';
  set local role authenticated;
  r := public.market_buy(lid);
  perform pg_temp.check(r->>'error' = 'market.err_buy_limit', 'daily buy count cap ' || r::text);
  reset role;
  update public.market_config set value = value || '{"max_listings_per_day": 20, "max_buys_per_day": 30}' where key = 'market';
  set local role authenticated;
  r := public.market_buy(lid);
  perform pg_temp.check((r->>'ok')::boolean, 'buy after raising the caps ' || r::text);

  -- only signed-in players can call the market; the helpers are internal
  reset role;
  perform pg_temp.check(not has_function_privilege('anon', 'public.market_browse(text, text, boolean, text, integer, integer)', 'execute'), 'anon browse');
  perform pg_temp.check(not has_function_privilege('anon', 'public.market_join(text)', 'execute'), 'anon join');
  perform pg_temp.check(not has_function_privilege('anon', 'public.market_buy(uuid)', 'execute'), 'anon buy');
  perform pg_temp.check(not has_function_privilege('anon', 'public.market_claim(uuid, text)', 'execute'), 'anon claim');
  perform pg_temp.check(not has_function_privilege('anon', 'public.market_create_listing(jsonb, integer)', 'execute'), 'anon create');
  perform pg_temp.check(not has_function_privilege('authenticated', 'public.validate_item(jsonb)', 'execute'), 'helper internal');
  perform pg_temp.check(not has_function_privilege('authenticated', 'public._lock_player(uuid)', 'execute'), 'lock internal');
  perform pg_temp.check(has_function_privilege('authenticated', 'public.market_browse(text, text, boolean, text, integer, integer)', 'execute'), 'authenticated browse');
  perform set_config('request.jwt.claim.sub', '', false);
  set local role anon;
  begin
    perform public.market_browse('', '', false, 'price', 40, 0);
    raise exception 'CHECK FAILED: anon ran market_browse';
  exception when insufficient_privilege then null;
  end;
  reset role;
  set local role authenticated;
  r := public.market_browse('', '', false, 'price', 40, 0);
  perform pg_temp.check(r->>'error' = 'market.err_auth', 'browse needs a user ' || r::text);
  reset role;
  perform set_config('request.jwt.claim.sub', a, false);
  set local role authenticated;

  -- tables can't be written directly
  begin
    insert into public.listings (seller, seller_name, item_uid, item, slot, rarity, price, expires_at)
      values (a::uuid, 'x', 'z1', '{}', 'helm', 'rare', 1, now());
    raise exception 'CHECK FAILED: direct insert allowed';
  exception when insufficient_privilege then null;
  end;
  update public.mailbox set gold = 999999 where owner = a::uuid;
  update public.listings set price = 1 where true;
  reset role;
  perform pg_temp.check(not exists (select 1 from public.mailbox where gold = 999999), 'direct mailbox update blocked');
  perform pg_temp.check(not exists (select 1 from public.listings where price = 1), 'direct listing update blocked');
  reset role;
  raise notice 'market tests passed';
end $$;
