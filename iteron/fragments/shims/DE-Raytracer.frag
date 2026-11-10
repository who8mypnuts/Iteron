#donotrun
// SPDX-License-Identifier: MIT
// Iteron's stand-in for Fragmentarium's ray tracers (DE-Raytracer.frag, 3D.frag and their relatives).
// Iteron meshes and previews a fragment's distance estimator itself, so the "ray tracer" only provides what a
// DE may touch: the orbit trap the colours come from, and the tracer's and camera's settings as fixed values
// (Iteron's compatibility pass gives them their usual defaults). Written for Iteron; not derived from FragM.
#define ITERON_HOST 1
vec4 orbitTrap = vec4(10000.0);
float fractionalCount = 0.0;
float DE(vec3 pos);

uniform float FOV;
uniform vec3 Eye;
uniform vec3 Target;
uniform vec3 Up;
uniform float time;
uniform int subframe;
uniform vec2 pixelSize;
uniform float Detail;
uniform float DetailAO;
uniform float FudgeFactor;
uniform float MaxDistance;
uniform int MaxRaySteps;
uniform float Dither;
uniform float NormalBackStep;
uniform float Specular;
uniform float SpecularExp;
uniform float Fog;
uniform float HardShadow;
uniform float ShadowSoft;
uniform float Reflection;
uniform vec3 BaseColor;
uniform float OrbitStrength;
uniform vec3 BackgroundColor;
uniform float GradientBackground;
uniform bool CycleColors;
uniform float Cycles;
uniform bool EnableFloor;
uniform vec3 FloorNormal;
uniform float FloorHeight;
uniform vec3 FloorColor;
uniform vec4 SpotLight;
uniform vec3 SpotLightPos;
uniform vec2 SpotLightDir;
uniform vec4 CamLight;
uniform vec4 Glow;
uniform vec4 AO;
