#version 120

uniform vec2 iResolution;
uniform vec2 iMouse;
uniform vec2 iMouseScale;
uniform vec2 iViewportOrigin;
uniform float iTime;

vec3 palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(0.263, 0.416, 0.557);

    return a + b * cos(6.28318 * (c * t + d));
}

void main() {
    vec2 fragCoord = gl_FragCoord.xy - iViewportOrigin;
    vec2 uv = (fragCoord * 2.0 - iResolution.xy) / iResolution.y;
    vec2 uv0 = uv;
    vec2 m = ((iMouse.xy * 2.0 - iResolution.xy) / iResolution.y) * iMouseScale;
    vec3 finalColor = vec3(0.0);
    float cursorX = max(abs(m.x), 0.08);
    cursorX *= sign(m.x == 0.0 ? 1.0 : m.x);

    for (float i = 0.0; i < 4.0; i++) {
        uv = fract(uv * cursorX) - 0.5;

        float d = length(uv) * exp(-length(uv0));
        vec3 col = palette(length(uv0) + i * 0.4 + iTime * 0.4);

        d = sin(d * 8.0 + iTime) / 8.0;
        d = abs(d);
        d = pow(0.01 / max(d, 0.0001), 1.2);

        finalColor += col * d;
    }

    gl_FragColor = vec4(finalColor * max(abs(m.y), 0.08), 1.0);
}
