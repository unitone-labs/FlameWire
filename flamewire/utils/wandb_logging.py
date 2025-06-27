import os
import bittensor as bt

try:
    import wandb
except Exception:
    wandb = None


def init_wandb(config, **kwargs):
    """Initialize wandb using config flags.

    Args:
        config: bt.config with wandb.off, wandb.offline and wandb.notes
        kwargs: additional arguments passed to ``wandb.init``

    Returns:
        The ``wandb`` module if initialization succeeded, otherwise ``None``.
    """
    if wandb is None:
        bt.logging.warning("wandb package not installed, skipping initialization")
        return None

    if getattr(config, "wandb", None) is None or config.wandb.off:
        bt.logging.info("wandb disabled via configuration")
        return None

    mode = "offline" if config.wandb.offline else "online"
    os.environ.setdefault("WANDB_SILENT", "true")
    try:
        wandb.init(mode=mode, notes=config.wandb.notes, **kwargs)
        bt.logging.info(f"wandb initialized in {mode} mode")
        return wandb
    except Exception as e:
        bt.logging.warning(f"Failed to initialize wandb: {e}")
        return None
