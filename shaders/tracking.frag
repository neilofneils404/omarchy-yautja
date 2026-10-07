#version 300 es
// Yautja vision: tracking. Red monochrome with scanlines and a vignette.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
  vec4 px = texture(tex, v_texcoord);
  float l = dot(px.rgb, vec3(0.299, 0.587, 0.114));
  l = smoothstep(0.02, 0.95, l);
  vec3 col = mix(vec3(0.060, 0.000, 0.005), vec3(1.000, 0.130, 0.060), l);
  col += vec3(1.0, 0.75, 0.45) * pow(l, 6.0) * 0.55;
  float scan = 0.88 + 0.12 * step(1.0, mod(gl_FragCoord.y, 3.0));
  vec2 d = v_texcoord - 0.5;
  float vignette = 1.0 - dot(d, d) * 0.9;
  fragColor = vec4(col * scan * vignette, px.a);
}
