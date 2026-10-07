#version 300 es
// Yautja vision: electromagnetic. Cyan-green phosphor over a dark violet
// field, with solid glyphs and a continuous luminance ramp for readable text.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
  // Sample only this pixel: neighbour-based glow thickens small glyphs and
  // makes their outlines unstable as antialiased content moves.
  vec4 src = texture(tex, v_texcoord);
  float base = clamp(dot(src.rgb, vec3(0.299, 0.587, 0.114)), 0.0, 1.0);
  vec3 field = mix(vec3(0.018, 0.012, 0.045), vec3(0.620, 0.980, 0.850), base);
  // Retain some source colour to help distinguish syntax and UI accents.
  fragColor = vec4(mix(field, src.rgb, 0.20), src.a);
}
