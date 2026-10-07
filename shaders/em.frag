#version 300 es
// Yautja vision: electromagnetic. Edges glow cyan-green over a dark violet
// field, so structure shows and flat fills fall away.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

float luma(vec2 uv) {
  return dot(texture(tex, uv).rgb, vec3(0.299, 0.587, 0.114));
}

void main() {
  vec2 px = 1.0 / vec2(textureSize(tex, 0));
  float tl = luma(v_texcoord + px * vec2(-1.0, -1.0));
  float tc = luma(v_texcoord + px * vec2( 0.0, -1.0));
  float tr = luma(v_texcoord + px * vec2( 1.0, -1.0));
  float ml = luma(v_texcoord + px * vec2(-1.0,  0.0));
  float mr = luma(v_texcoord + px * vec2( 1.0,  0.0));
  float bl = luma(v_texcoord + px * vec2(-1.0,  1.0));
  float bc = luma(v_texcoord + px * vec2( 0.0,  1.0));
  float br = luma(v_texcoord + px * vec2( 1.0,  1.0));
  float gx = -tl - 2.0 * ml - bl + tr + 2.0 * mr + br;
  float gy = -tl - 2.0 * tc - tr + bl + 2.0 * bc + br;
  float edge = clamp(length(vec2(gx, gy)) * 1.6, 0.0, 1.0);

  vec4 src = texture(tex, v_texcoord);
  float base = dot(src.rgb, vec3(0.299, 0.587, 0.114));
  vec3 field = mix(vec3(0.035, 0.010, 0.085), vec3(0.230, 0.060, 0.420), base);
  vec3 glow = mix(vec3(0.100, 1.000, 0.650), vec3(0.850, 1.000, 1.000), edge);
  fragColor = vec4(field + glow * edge + vec3(0.0, 0.55, 0.45) * base * 0.45, src.a);
}
