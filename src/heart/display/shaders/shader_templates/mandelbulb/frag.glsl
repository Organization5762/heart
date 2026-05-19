#version 120

uniform vec2 iResolution;
uniform float iTime;
uniform float uCameraYaw;
uniform float uCameraPitch;
uniform float uCameraDistance;
uniform float uPower;
uniform float uColorPhase;
uniform vec2 uColorVector;
uniform float uColorMode;
uniform float uPhaseTime;
uniform float uAutoYaw;

const int MANDELBULB_ITERATIONS = 7;
const int RAYMARCH_STEPS = 48;
const int SHADOW_STEPS = 0;

void rotateY(inout vec3 p, float a) {
    float c = cos(a);
    float s = sin(a);
    vec3 q = p;
    p.x = c * q.x + s * q.z;
    p.z = -s * q.x + c * q.z;
}

vec3 mandelbulbMap(vec3 p) {
    p.xyz = p.xzy;
    vec3 z = p;
    float power = uPower;
    float r = 1.0;
    float theta = 0.0;
    float phi = 0.0;
    float dr = 1.0;
    float orbit = 1.0;

    for (int i = 0; i < MANDELBULB_ITERATIONS; ++i) {
        r = length(z);
        if (r <= 2.0) {
            theta = atan(z.y, z.x);
            phi = asin(clamp(z.z / max(r, 0.0001), -1.0, 1.0)) + uPhaseTime * 0.1;
            dr = pow(r, power - 1.0) * dr * power + 1.0;

            r = pow(r, power);
            theta *= power;
            phi *= power;

            z = r * vec3(
                cos(theta) * cos(phi),
                sin(theta) * cos(phi),
                sin(phi)
            ) + p;
            orbit = min(orbit, r);
        }
    }

    return vec3(0.5 * log(r) * r / dr, orbit, 0.0);
}

vec3 field(vec3 p) {
    rotateY(p, uAutoYaw * 1.6666667);
    return mandelbulbMap(p);
}

float softShadow(vec3 ro, vec3 rd, float k) {
    float shade = 1.0;
    float h = 0.0;
    float t = 0.01;

    for (int i = 0; i < SHADOW_STEPS; ++i) {
        h = field(ro + rd * t).x;
        if (h < 0.001) {
            return 0.02;
        }
        shade = min(shade, k * h / t);
        t += clamp(h, 0.01, 2.0);
    }

    return shade;
}

vec3 normalAt(vec3 pos) {
    vec3 eps = vec3(0.001, 0.0, 0.0);
    return normalize(vec3(
        field(pos + eps.xyy).x - field(pos - eps.xyy).x,
        field(pos + eps.yxy).x - field(pos - eps.yxy).x,
        field(pos + eps.yyx).x - field(pos - eps.yyx).x
    ));
}

vec3 intersectScene(vec3 ro, vec3 rd, float pixel_size) {
    float t = 1.0;
    float res_t = 0.0;
    vec3 c = vec3(0.0);
    vec3 res_c = vec3(0.0);
    float max_error = 1000.0;
    float d = 1.0;
    float pd = 100.0;
    float os = 0.0;
    float step_size = 0.0;
    float error = 1000.0;

    for (int i = 0; i < RAYMARCH_STEPS; i++) {
        if (error >= pixel_size * 0.5 && t <= 20.0) {
            c = field(ro + rd * t);
            d = c.x;

            if (d > os) {
                os = 0.4 * d * d / pd;
                step_size = d + os;
                pd = d;
            } else {
                step_size = -os;
                os = 0.0;
                pd = 100.0;
                d = 1.0;
            }

            error = d / t;

            if (error < max_error) {
                max_error = error;
                res_t = t;
                res_c = c;
            }

            t += step_size;
        }
    }

    if (t > 20.0) {
        res_t = -1.0;
    }
    return vec3(res_t, res_c.y, res_c.z);
}

vec3 tintedPalette(float phase, vec3 offsets, vec3 tint) {
    return clamp((0.5 + 0.5 * sin(phase + offsets)) * tint, 0.0, 1.25);
}

vec3 quadrantPalette(vec2 color_vector, float orbit) {
    float color_amount = clamp(length(color_vector), 0.0, 1.0);
    vec2 color_dir = color_vector / max(color_amount, 0.0001);
    vec4 weights = vec4(
        max(color_dir.x, 0.0),
        max(color_dir.y, 0.0),
        max(-color_dir.x, 0.0),
        max(-color_dir.y, 0.0)
    );
    weights /= max(dot(weights, vec4(1.0)), 0.0001);

    float phase = 3.0 + uColorPhase + 4.2 * orbit;
    vec3 warm = tintedPalette(
        phase,
        vec3(0.0, 0.85, 1.85),
        vec3(1.25, 0.72, 0.34)
    );
    vec3 cyan = tintedPalette(
        phase,
        vec3(2.6, 0.85, 0.05),
        vec3(0.42, 1.06, 1.18)
    );
    vec3 violet = tintedPalette(
        phase,
        vec3(1.15, 0.05, 2.9),
        vec3(0.95, 0.48, 1.2)
    );
    vec3 acid = tintedPalette(
        phase,
        vec3(2.85, 0.15, 1.35),
        vec3(0.48, 1.15, 0.42)
    );

    return warm * weights.x
        + cyan * weights.y
        + violet * weights.z
        + acid * weights.w;
}

vec3 angleWheelPalette(vec2 color_vector, float orbit) {
    float color_angle = atan(color_vector.y, color_vector.x);
    return 0.5 + 0.5 * sin(
        3.0 + uColorPhase + color_angle + 4.2 * orbit + vec3(0.0, 2.094, 4.188)
    );
}

vec3 denseBandPalette(vec2 color_vector, float orbit) {
    float amount = clamp(length(color_vector), 0.0, 1.0);
    float color_angle = atan(color_vector.y, color_vector.x);
    float band_phase = 3.0 + uColorPhase + color_angle + mix(3.0, 12.0, amount) * orbit;
    vec3 broad = 0.5 + 0.5 * sin(band_phase + vec3(0.0, 1.4, 2.8));
    vec3 tight = 0.5 + 0.5 * sin(band_phase * 1.7 + vec3(2.2, 0.4, 1.1));
    return mix(broad, tight, amount * 0.55);
}

vec3 prismPalette(vec2 color_vector, float orbit) {
    float amount = clamp(length(color_vector), 0.0, 1.0);
    float color_angle = atan(color_vector.y, color_vector.x);
    vec3 base = 0.5 + 0.5 * sin(
        3.0 + uColorPhase + color_angle + 4.8 * orbit + vec3(0.0, 2.094, 4.188)
    );
    vec3 complement = 0.5 + 0.5 * sin(
        3.0 + uColorPhase + color_angle + 3.14159 - 6.2 * orbit + vec3(0.0, 2.094, 4.188)
    );
    return mix(base, complement, 0.25 + 0.5 * amount);
}

vec3 stickPalette(vec2 color_vector, float orbit) {
    if (uColorMode < 0.5) {
        return quadrantPalette(color_vector, orbit);
    }
    if (uColorMode < 1.5) {
        return angleWheelPalette(color_vector, orbit);
    }
    if (uColorMode < 2.5) {
        return denseBandPalette(color_vector, orbit);
    }
    return prismPalette(color_vector, orbit);
}

void main() {
    vec2 q = gl_FragCoord.xy / iResolution.xy;
    vec2 uv = -1.0 + 2.0 * q;
    uv.x *= iResolution.x / iResolution.y;

    float pixel_size = 1.0 / (iResolution.x * 3.0);
    float yaw = uAutoYaw + uCameraYaw;
    float pitch = 0.45 + uCameraPitch;
    float cp = cos(pitch);

    vec3 target = vec3(0.0);
    vec3 ro = uCameraDistance * vec3(sin(yaw) * cp, sin(pitch), cos(yaw) * cp);
    vec3 cf = normalize(target - ro);
    vec3 cs = normalize(cross(cf, vec3(0.0, 1.0, 0.0)));
    vec3 cu = normalize(cross(cs, cf));
    vec3 rd = normalize(uv.x * cs + uv.y * cu + 3.0 * cf);

    vec3 sundir = normalize(vec3(0.1, 0.8, 0.6));
    vec3 sun = vec3(1.64, 1.27, 0.99);
    vec3 skycolor = vec3(0.6, 1.5, 1.0);
    vec3 bg = exp(uv.y - 2.0) * vec3(0.4, 1.6, 1.0);
    float halo = clamp(dot(normalize(-ro), rd), 0.0, 1.0);
    vec3 col = bg + vec3(1.0, 0.8, 0.4) * pow(halo, 17.0);

    vec3 res = intersectScene(ro, rd, pixel_size);
    if (res.x > 0.0) {
        vec3 p = ro + res.x * rd;
        vec3 n = normalAt(p);
        float shadow = softShadow(p, sundir, 10.0);
        float dif = max(0.0, dot(n, sundir));
        float sky = 0.6 + 0.4 * max(0.0, dot(n, vec3(0.0, 1.0, 0.0)));
        float bac = max(0.3 + 0.7 * dot(vec3(-sundir.x, -1.0, -sundir.z), n), 0.0);
        float spe = pow(clamp(dot(sundir, reflect(rd, n)), 0.0, 1.0), 10.0);

        vec3 lin = 4.5 * sun * dif * shadow;
        lin += 0.8 * bac * sun;
        lin += 0.6 * sky * skycolor * shadow;
        lin += 3.0 * spe * shadow;

        float orbit = pow(clamp(res.y, 0.0, 1.0), 0.55);
        vec3 auto_palette = 0.5 + 0.5 * sin(
            3.0 + uColorPhase + 4.2 * orbit + vec3(0.0, 0.5, 1.0)
        );
        float color_amount = clamp(length(uColorVector), 0.0, 1.0);
        vec3 stick_palette = stickPalette(uColorVector, orbit);
        vec3 tc0 = mix(auto_palette, stick_palette, color_amount);
        col = lin * vec3(0.9, 0.8, 0.6) * 0.2 * tc0;
        col = mix(col, bg, 1.0 - exp(-0.001 * res.x * res.x));
    }

    col = pow(clamp(col, 0.0, 1.0), vec3(0.45));
    col = col * 0.6 + 0.4 * col * col * (3.0 - 2.0 * col);
    col = mix(col, vec3(dot(col, vec3(0.33))), -0.5);
    col *= 0.5 + 0.5 * pow(16.0 * q.x * q.y * (1.0 - q.x) * (1.0 - q.y), 0.7);

    gl_FragColor = vec4(col, 1.0);
}
