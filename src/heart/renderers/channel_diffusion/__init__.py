from heart.peripheral.core.providers import register_provider
from heart.renderers.channel_diffusion.provider import \
    ChannelDiffusionStateProvider as ChannelDiffusionStateProvider
from heart.renderers.channel_diffusion.renderer import \
    ChannelDiffusionRenderer as ChannelDiffusionRenderer
from heart.renderers.channel_diffusion.state import \
    ChannelDiffusionState as ChannelDiffusionState

register_provider(ChannelDiffusionStateProvider, ChannelDiffusionStateProvider)
