#version 120

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_orbit_phase;
uniform sampler2D u_audio;

vec2 mirror_repeat(vec2 value) {
    vec2 wrapped = fract(value * 0.5) * 2.0;
    return 1.0 - abs(wrapped - 1.0);
}

void main() {
    vec4 fragColor = vec4(0.0);
    for (float i = 0.0; i < 100.0; i += 1.0) {
        vec2 c = (
            (2.0 * gl_FragCoord.xy - u_resolution) / u_resolution.y * 55.0
            - vec2(0.0, i - 50.0) * 0.3
        ) * vec2(1.0, 2.0) * mat2(cos(u_orbit_phase + vec4(0.0, 33.0, 11.0, 0.0)));

        float energy = texture2D(u_audio, mirror_repeat(c / vec2(512.0, 100.0))).b;
        float falloff = exp(abs(100.0 * energy / (1.0 + abs(c.y) / 10.0) - i));
        fragColor.rgb += (vec3(sqrt(i / 100.0)) - fragColor.rgb) / falloff;
    }

    vec3 color = fragColor.rgb;
    color *= vec3(0.78, 0.68, 1.25);
    color += vec3(0.05, 0.12, 0.22) * pow(clamp(color.b, 0.0, 1.0), 2.0);
    color += vec3(0.006, 0.008, 0.018);
    gl_FragColor = vec4(pow(clamp(color, 0.0, 1.0), vec3(0.82)), 1.0);
}
