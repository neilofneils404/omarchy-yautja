#version 300 es
// Yautja vision: thermal. Luminance is read as heat and mapped onto a
// cold-blue -> magenta -> red -> yellow -> white-hot ramp.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

vec3 ramp(float t) {
  const vec3 c0 = vec3(0.010, 0.012, 0.090);
  const vec3 c1 = vec3(0.050, 0.070, 0.520);
  const vec3 c2 = vec3(0.420, 0.060, 0.640);
  const vec3 c3 = vec3(0.930, 0.110, 0.200);
  const vec3 c4 = vec3(1.000, 0.520, 0.050);
  const vec3 c5 = vec3(1.000, 0.900, 0.150);
  const vec3 c6 = vec3(1.000, 1.000, 0.940);
  t = clamp(t, 0.0, 1.0) * 6.0;
  if (t < 1.0) return mix(c0, c1, t);
  if (t < 2.0) return mix(c1, c2, t - 1.0);
  if (t < 3.0) return mix(c2, c3, t - 2.0);
  if (t < 4.0) return mix(c3, c4, t - 3.0);
  if (t < 5.0) return mix(c4, c5, t - 4.0);
  return mix(c5, c6, t - 5.0);
}

void main() {
  vec4 px = texture(tex, v_texcoord);
  float heat = dot(px.rgb, vec3(0.299, 0.587, 0.114));
  // Saturated pixels run a little hotter than grey ones of the same luma.
  float sat = max(px.r, max(px.g, px.b)) - min(px.r, min(px.g, px.b));
  heat = clamp(heat + sat * 0.18, 0.0, 1.0);
  heat = pow(heat, 0.85);
  // Soft banding, like the stepped isotherms of a thermal imager.
  heat = mix(heat, floor(heat * 18.0 + 0.5) / 18.0, 0.35);
  fragColor = vec4(ramp(heat), px.a);
}
