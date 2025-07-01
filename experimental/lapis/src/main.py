import numpy as np
import mcubes

import taichi as ti
import taichi.math as tm

ti.init(arch=ti.cuda)

n = 320
pixels = ti.field(dtype=float, shape=(n * 1, n))


@ti.func
def complex_sqr(z):  # complex square of a 2D vector
    return tm.vec2(z[0] * z[0] - z[1] * z[1], 2 * z[0] * z[1])

@ti.kernel
def paint(t: float):
    for i, j in pixels:  # Parallelized over all pixels
        c = tm.vec2(-0.8, tm.cos(t) * 0.2)
        z = tm.vec2(i / n - 1, j / n - 0.5) * 2
        iterations = 0
        while z.norm() < 20 and iterations < 50:
            z = complex_sqr(z) + c
            iterations += 1
        pixels[i, j] = 1 - iterations * 0.02

def _compute_volume(seed: int = 0):
    x, y, z = np.mgrid[:100, :100, :100]
    return (x - 50)**2 + (y - 50)**2 + (z - 50)**2 - 25**2 < 0

def _create_mesh(volume):
    smoothed = mcubes.smooth(volume)
    mesh = mcubes.marching_cubes(smoothed, 0)
    return mesh





def main():
    volume = _compute_volume()
    mesh = _create_mesh(volume)
    mcubes.export_mesh(mesh, "sphere.obj", "sphere")


if __name__ == "__main__":
    # main()
    gui = ti.GUI("Julia Set", res=(n * 2, n))

    i = 0
    while gui.running:
        paint(i * 0.03)
        gui.set_image(pixels)
        gui.show()
        i += 1
