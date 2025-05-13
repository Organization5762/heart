import numpy as np

from numba import jit

# I took this shader https://www.shadertoy.com/view/M3VcRt and had Cursor convert it to Python.

@jit(nopython=True, fastmath=True)
def voronoi(uv: np.ndarray) -> float:
    """
    Calculate Voronoi noise for a given UV coordinate.
    
    Args:
        uv: 2D numpy array representing UV coordinates
        
    Returns:
        float: Voronoi noise value
    """
    i = np.floor(uv)
    f = uv - i
    min_dist1 = 1.0
    min_dist2 = 1.0
    
    for y in range(-1, 2):
        for x in range(-1, 2):
            neighbor = np.array([float(x), float(y)])
            point = np.array([
                np.fmod(np.sin(np.dot(i + neighbor, np.array([127.1, 311.7]))) * 43758.5453, 1.0),
                np.fmod(np.sin(np.dot(i + neighbor, np.array([311.7, 127.1]))) * 43758.5453, 1.0)
            ])
            diff = neighbor + point - f
            dist = np.sqrt(np.sum(diff * diff))
            
            step1 = 1.0 - np.where(dist >= min_dist1, 1.0, 0.0)
            step2 = 1.0 - np.where(dist >= min_dist2, 1.0, 0.0)
            
            min_dist2 = (min_dist1 * step1 + 
                        (1.0 - step1) * (step2 * dist) + 
                        ((1.0 - step1) * (1.0 - step2)) * min_dist2)
            min_dist1 = dist * step1 + (1.0 - step1) * min_dist1
            
    return min_dist2 - min_dist1

class WaterEffect:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.time = 0.0
        
        # Water effect parameters
        self.voronoi_scale = 10.0
        self.distortion1_strength = 0.12
        self.distortion1_frequency = 0.5
        self.distortion1_speed = 0.8
        self.edge1_threshold_min = 0.01
        self.edge1_threshold_max = 0.26
        self.edge2_threshold_min = 0.28
        self.edge2_threshold_max = 0.36
        
        # Colors
        self.main_blue = np.array([0.0, 0.7, 1.0])
        self.light_blue = np.array([0.3, 0.85, 1.0])
        self.foam_color = np.array([0.9, 1.0, 1.0])
    
    def update(self, dt: float):
        """Update the water effect with time delta."""
        self.time += dt
    
    def render(self) -> np.ndarray:
        """
        Render the water effect.
        
        Returns:
            np.ndarray: RGB image array of shape (width, height, 3)
        """
        # Create coordinate grid
        x, y = np.mgrid[0:self.width, 0:self.height]
        frag_coord = np.stack([x, y], axis=-1)
        
        # Pixelate coordinates
        uv = (frag_coord + np.array([256.0, 256.0])) / np.array([self.width, self.height])
        
        # Calculate distorted UV coordinates
        distorted_uv = uv + np.array([
            np.sin(self.time * self.distortion1_speed + uv[..., 1] * self.distortion1_frequency) * self.distortion1_strength,
            np.cos(self.time * self.distortion1_speed + uv[..., 0] * self.distortion1_frequency) * self.distortion1_strength
        ]).transpose(1, 2, 0)
        
        # Calculate Voronoi noise and edges
        edge_dist1 = np.array([[voronoi(coord * self.voronoi_scale) for coord in row] for row in distorted_uv])
        
        # Calculate edge effects
        edges1 = np.clip((edge_dist1 - self.edge1_threshold_min) / 
                        (self.edge1_threshold_max - self.edge1_threshold_min), 0, 1)
        edge1_halo = np.clip((edge_dist1 - 0.1) / 0.4, 0, 1)
        edges2 = np.clip((edge_dist1 - self.edge2_threshold_min) / 
                        (self.edge2_threshold_max - self.edge2_threshold_min), 0, 1)
        
        # Mix colors
        e = np.where(edges2[:, :, np.newaxis] > 0.5,
                    self.light_blue, 
                    self.foam_color)
        e = np.where(edges1[:, :, np.newaxis] > 0.5,
                    self.main_blue,
                    e)
        
        # Apply halo effect
        e *= 0.1 + 1.0 - edge1_halo[:, :, np.newaxis] * 0.1
        
        return np.clip(e, 0, 1)
