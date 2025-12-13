from heart.display.renderers.metadata_screen.provider import \
    MetadataScreenStateProvider
from heart.display.renderers.metadata_screen.renderer import \
    MetadataScreen  # noqa: F401
from heart.display.renderers.metadata_screen.state import \
    MetadataScreenState  # noqa: F401
from heart.peripheral.core.providers import container

container[MetadataScreenStateProvider] = MetadataScreenStateProvider
