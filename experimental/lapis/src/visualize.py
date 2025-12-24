import taichi as ti

ti.init(arch=ti.cuda)


# Time
dt = 1.0 / 60.0


# Cube Variables
cube_res = (256, 256, 256)
spacing = 0.1
norm = cube_res[0] / 8
X = ti.Vector.field(3, dtype=ti.f32, shape=cube_res)  # positions
n_particles = cube_res[0] * cube_res[1] * cube_res[2]
X_flat = ti.Vector.field(3, dtype=ti.f32, shape=n_particles)


@ti.kernel
def initialize_mass_points():
    for i, j, k in X:
        # lay out the points on a regular grid
        X[i, j, k] = ti.Vector([i * spacing, j * spacing, k * spacing])


@ti.kernel
def flatten_for_render():
    for p in range(n_particles):
        i = p // (cube_res[1] * cube_res[2])
        j = (p // cube_res[2]) % cube_res[1]
        k = p % cube_res[2]
        X_flat[p] = X[i, j, k] / norm


def visualize():
    window = ti.ui.Window(
        "Taichi Cloth Simulation on GGUI", (1024, 1024), fps_limit=200
    )
    #  vsync=True)
    canvas = window.get_canvas()
    canvas.set_background_color((0, 0, 0))
    scene = ti.ui.Scene()
    camera = ti.ui.Camera()

    initialize_mass_points()
    frame = 0

    while window.running:
        camera.position(2.0, 2.0, 2.0)
        camera.lookat(0.5, 0.5, 0.5)
        camera.fov(45)
        scene.set_camera(camera)
        scene.point_light(pos=(0, 1, 2), color=(1, 1, 1))
        scene.ambient_light((0.5, 0.5, 0.5))

        flatten_for_render()
        v = frame / dt
        # Use smaller radii (e.g. 1.0 / norm) to emulate a denser, pixel-like view.
        scene.particles(
            X_flat,
            radius=spacing / norm,
            color=(((v % 256) / 256.0), ((v % 256) / 256.0), ((v % 256) / 256.0)),
        )

        canvas.scene(scene)
        window.show()

        frame += 1


if __name__ == "__main__":
    visualize()
