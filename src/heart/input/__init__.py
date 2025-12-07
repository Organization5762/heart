"""Input utilities for handling both local and remote input."""
import pygame


def get_key_pressed(key: int = None) -> bool | list:
    """Get keyboard state that works with both local and remote input.
    
    This is a drop-in replacement for pygame.key.get_pressed() that also
    checks remote keyboard state from WebSocket streaming.
    
    Args:
        key: Optional pygame key constant. If provided, returns bool for that key.
             If None, returns a list-like object with all key states.
    
    Returns:
        If key is provided: bool indicating if key is pressed (local OR remote)
        If key is None: RemoteKeySequence object that works like pygame.key.get_pressed()
    
    Usage:
        # Check a specific key
        if get_key_pressed(pygame.K_w):
            move_forward()
        
        # Get all keys (works with indexing)
        keys = get_key_pressed()
        if keys[pygame.K_w]:
            move_forward()
    """
    from heart.environment import GameLoop
    
    # Get local keyboard state
    local_keys = pygame.key.get_pressed()
    
    # Try to get remote keyboard state from broadcaster
    game_loop = GameLoop.get_game_loop()
    broadcaster = game_loop._broadcaster if game_loop else None
    
    if key is not None:
        # Return state for specific key
        local_pressed = local_keys[key]
        remote_pressed = broadcaster.get_key_pressed(key) if broadcaster else False
        return local_pressed or remote_pressed
    else:
        # Return RemoteKeySequence that can be indexed
        return RemoteKeySequence(local_keys, broadcaster)


class RemoteKeySequence:
    """A sequence-like object that merges local and remote keyboard state.
    
    This allows code like:
        keys = get_key_pressed()
        if keys[pygame.K_w]:
            ...
    """
    
    def __init__(self, local_keys, broadcaster):
        self.local_keys = local_keys
        self.broadcaster = broadcaster
    
    def __getitem__(self, key):
        """Get state of a specific key (local OR remote)."""
        local_pressed = self.local_keys[key]
        remote_pressed = self.broadcaster.get_key_pressed(key) if self.broadcaster else False
        return local_pressed or remote_pressed
    
    def __len__(self):
        """Return number of keys (same as pygame.key.get_pressed())."""
        return len(self.local_keys)

