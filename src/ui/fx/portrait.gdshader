shader_type canvas_item;
// Round portrait: shows the part of the texture around `center` (UV) zoomed by `zoom`,
// cut to a soft circle, over a dark vignette so busts and heads read in a medallion.

uniform vec2 center = vec2(0.5, 0.3);
uniform float zoom = 2.2;
uniform bool mirror = false;
uniform vec4 backdrop : source_color = vec4(0.10, 0.08, 0.12, 1.0);

void fragment() {
	vec2 uv = UV;
	if (mirror) {
		uv.x = 1.0 - uv.x;
	}
	vec2 src = center + (uv - vec2(0.5)) / zoom;
	vec4 tex = texture(TEXTURE, src);
	if (src.x < 0.0 || src.x > 1.0 || src.y < 0.0 || src.y > 1.0) {
		tex = vec4(0.0);
	}
	float d = distance(UV, vec2(0.5));
	vec3 bg = mix(backdrop.rgb * 1.8, backdrop.rgb, smoothstep(0.0, 0.5, d));
	vec3 rgb = mix(bg, tex.rgb, tex.a);
	float mask = 1.0 - smoothstep(0.47, 0.5, d);
	COLOR = vec4(rgb, mask);
}
