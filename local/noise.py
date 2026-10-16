"""Noise models for Quantum Oracle Forensics simulator.

Implements:
- Oracle misfire: oracle gate acts as identity with probability p_misfire.
- Readout bit-flip: each measured classical bit is flipped with probability p_flip.
- Preset configurations: NOISELESS, BASE_NOISE, STRESS_NOISE.
"""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class NoiseModel:
    p_misfire: float
    p_flip: float

    def sample_misfire(self, rng: np.random.Generator) -> bool:
        """Returns True if oracle application misfires (acts as identity)."""
        if self.p_misfire <= 0.0:
            return False
        return rng.random() < self.p_misfire

    def apply_readout_flips(self, bits: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Applies independent bit-flip noise to an array of measured bits."""
        if self.p_flip <= 0.0 or len(bits) == 0:
            return bits.copy()
        flip_mask = rng.random(len(bits)) < self.p_flip
        return bits ^ flip_mask.astype(int)


# Standard configurations defined by the hackathon challenge
NOISELESS = NoiseModel(p_misfire=0.0, p_flip=0.0)
BASE_NOISE = NoiseModel(p_misfire=0.04, p_flip=0.02)
STRESS_NOISE = NoiseModel(p_misfire=0.08, p_flip=0.04)
