from heart.peripheral.core.providers import register_provider
from heart.renderers.metadata_screen.provider import \
    MetadataScreenStateProvider
from heart.renderers.metadata_screen.renderer import \
    MetadataScreen  # noqa: F401
from heart.renderers.metadata_screen.state import \
    MetadataScreenState  # noqa: F401

register_provider(MetadataScreenStateProvider, MetadataScreenStateProvider)
