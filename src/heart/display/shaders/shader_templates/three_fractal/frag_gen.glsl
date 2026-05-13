#version 120
#define M_PI 3.14159265358979

uniform mat4 iMat;
uniform vec2 iResolution;

// Constants
const float AMBIENT_OCCLUSION_STRENGTH = 0.01;
const vec3 AMBIENT_OCCLUSION_COLOR_DELTA = vec3(0.8, 0.8, 0.8);
const vec3 BACKGROUND_COLOR = vec3(0.15, 0.15, 0.15);
const float EXPOSURE = 1.0;
const float FIELD_OF_VIEW = 60.0;
const vec3 LIGHT_COLOR = vec3(1.0, 0.9, 0.6);
const vec3 LIGHT_DIRECTION = vec3(-0.36, 0.48, 0.8);
// const vec3 ORBIT_COLOR = vec3(0.5, 0.5, 0.5);
const float LOD_MULTIPLIER = 10.0;
const int MAX_MARCHES = 1000;
const float MAX_DIST = 50.0;
const float MIN_DIST = 1e-05;
const float SHADOW_DARKNESS = 0.8;
const float SHADOW_SHARPNESS = 16.0;
const int SPECULAR_HIGHLIGHT = 40;
const float VIGNETTE_STRENGTH = 0.5;
const float GLOW_SHARPNESS = 4.0;
const float FOCAL_DIST = 1.0 / tan(M_PI * FIELD_OF_VIEW / 360.0);

// Uniform variable
uniform float _s_radius;
// uniform vec3 _orbit_color;
// const vec3 _orbit_color = vec3(1.0,0.078431375,0.8627451);
const vec3 _orbit_color = vec3(1.0,0.078431375,0.8627451);


// Forward declarations for distance estimator and coloring functions
float DE(vec4 p);
vec4 COL(vec4 p);

//A faster formula to find the gradient/normal direction of the DE
vec3 calcNormal(vec4 p, float dx) {
    const vec3 k = vec3(1, -1, 0);
    return normalize(k.xyy*DE(p + k.xyyz*dx) +
                     k.yyx*DE(p + k.yyxz*dx) +
                     k.yxy*DE(p + k.yxyz*dx) +
                     k.xxx*DE(p + k.xxxz*dx));
}

// Ray marching function
vec4 ray_march(inout vec4 p, vec4 ray, float sharpness, float td) {
    float d = MIN_DIST;
    float s = 0.0;
    float min_d = 1.0;

    for (; s < MAX_MARCHES; s += 1.0) {
        d = DE(p);
        if (d < MIN_DIST) {
            s += d / MIN_DIST;
            break;
        } else if (td > MAX_DIST) {
            break;
        }
        td += d;
        p += ray * d;
        min_d = min(min_d, sharpness * d / td);
    }

    return vec4(d, s, td, min_d);
}

// Overloaded version for vec3 ray
vec4 ray_march(inout vec4 p, vec3 ray, float sharpness, float td) {
    return ray_march(p, vec4(ray, 0.0), sharpness, td);
}

// Main scene rendering function
vec4 scene(inout vec4 origin, inout vec4 ray, float vignette, float td) {
    vec4 p = origin;
    vec4 d_s_td_m = ray_march(p, ray, GLOW_SHARPNESS, td);
    float d = d_s_td_m.x;
    float s = d_s_td_m.y;
    td = d_s_td_m.z;

    vec3 col = vec3(0.0);
    float min_dist = MIN_DIST * max(td * LOD_MULTIPLIER, 1.0);

    if (d < min_dist) {
        // Surface hit - calculate shading
        vec3 n = calcNormal(p, MIN_DIST * 10);
        vec3 reflected = ray.xyz - 2.0 * dot(ray.xyz, n) * n;

        // Get material color
        vec3 orig_col = clamp(COL(p).xyz, 0.0, 1.0);

        // Calculate shadows
        float k = 1.0;
        vec4 light_pt = p;
        light_pt.xyz += n * min_dist * 10;
        vec4 rm = ray_march(light_pt, LIGHT_DIRECTION, SHADOW_SHARPNESS, 0.0);
        k = rm.w * min(rm.z, 1.0);

        // Specular highlight
        if (SPECULAR_HIGHLIGHT > 0) {
            float specular = max(dot(reflected, LIGHT_DIRECTION), 0.0);
            specular = pow(specular, float(SPECULAR_HIGHLIGHT));
            col += specular * LIGHT_COLOR * k;
        }

        // Enhanced diffuse lighting
        k = min(k, SHADOW_DARKNESS * 0.5 * (dot(n, LIGHT_DIRECTION) - 1.0) + 1.0);

        // Don't make shadows entirely dark
        k = max(k, 1.0 - SHADOW_DARKNESS);
        col += orig_col * LIGHT_COLOR * k;

        // Add ambient occlusion
        float a = 1.0 / (1.0 + s * AMBIENT_OCCLUSION_STRENGTH);
        col += (1.0 - a) * AMBIENT_OCCLUSION_COLOR_DELTA;
    } else {
        // Ray missed - use background color
        col += BACKGROUND_COLOR;
        col *= vignette;
    }

    return vec4(col, td);
}

// Distance estimator function
float de_sphere(vec4 p, float r) {
    return (length(p.xyz) - r) / p.w;
}

// Main distance estimator
float DE(vec4 p) {
    vec4 o = p;
    float d = 1e20;
    p.xyz = abs(mod(p.xyz - 2.0/2, 2.0) - 2.0/2);
    d = min(d, de_sphere(p - vec4(vec3(1.0, 1.0, 1.0), 0), _s_radius));
    return d;
}

// Color function
vec4 COL(vec4 p) {
    vec4 o = p;
    vec4 col = vec4(1e20);
    vec4 newCol;
    vec3 orbit = vec3(0.0);
    p.xyz = abs(mod(p.xyz - 2.0/2, 2.0) - 2.0/2);
    orbit = max(orbit, (p.xyz - vec3(0.0, 0.0, 0.0)) * _orbit_color);
    newCol = vec4(orbit, de_sphere(p - vec4(vec3(1.0, 1.0, 1.0), 0), _s_radius));
    if (newCol.w < col.w) { col = newCol; }
    return col;
}

void main() {
    vec4 col = vec4(0.0);

    // Single sample AA
    vec2 screen_pos = gl_FragCoord.xy / iResolution.xy;
    vec2 uv = 2.0 * screen_pos - 1.0;
    uv.x *= iResolution.x / iResolution.y;

    // Create ray
    vec4 ray = normalize(vec4(uv.x, uv.y, -FOCAL_DIST, 0.0));
    ray = iMat * ray;

    // Set ray origin
    vec4 p = iMat[3];

    // Calculate vignette
    float vignette = 1.0 - VIGNETTE_STRENGTH * length(screen_pos - 0.5);

    // Render the scene
    col += scene(p, ray, vignette, 0.0);

    // Output final color
    gl_FragColor.rgb = clamp(col.xyz * EXPOSURE, 0.0, 1.0);
    gl_FragDepth = min(col.w / MAX_DIST, 0.999);
}