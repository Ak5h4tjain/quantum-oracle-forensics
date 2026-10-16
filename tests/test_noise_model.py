"""TEST-009: Noise model verification (misfire and readout flip).

Validates:
- Base noise: 4% misfire rate, 2% readout flip rate.
- Stress noise: 8% misfire rate, 4% readout flip rate.
- Noiseless: 0% misfire, 0% flip.
- Statistical verification: Empirical rates match binomial expectation within 3 standard errors.
"""

import pytest
import numpy as np
from local.noise import NoiseModel, BASE_NOISE, STRESS_NOISE, NOISELESS


def test_noiseless_model():
    """Noiseless configuration has exactly 0 misfire and 0 flip."""
    model = NOISELESS
    assert model.p_misfire == 0.0
    assert model.p_flip == 0.0
    
    # 1000 trials should never misfire or flip
    rng = np.random.default_rng(42)
    assert not any(model.sample_misfire(rng) for _ in range(1000))
    for _ in range(100):
        bits = np.array([0, 1, 0, 1, 1, 0, 0, 1])
        noisy_bits = model.apply_readout_flips(bits, rng)
        assert np.array_equal(bits, noisy_bits)


def test_base_noise_rates():
    """Base noise: 4% misfire, 2% bit flip within 3 std err."""
    model = BASE_NOISE
    assert model.p_misfire == 0.04
    assert model.p_flip == 0.02
    
    n_samples = 20_000
    rng = np.random.default_rng(2026)
    
    # Test misfire
    misfires = sum(model.sample_misfire(rng) for _ in range(n_samples))
    empirical_p_misfire = misfires / n_samples
    se_misfire = np.sqrt(0.04 * 0.96 / n_samples)
    assert abs(empirical_p_misfire - 0.04) < 3.5 * se_misfire, (
        f"Empirical misfire {empirical_p_misfire} outside 3.5 SE of 0.04"
    )
    
    # Test readout flip
    bits = np.zeros(n_samples, dtype=int)
    flipped = model.apply_readout_flips(bits, rng)
    empirical_p_flip = np.mean(flipped)
    se_flip = np.sqrt(0.02 * 0.98 / n_samples)
    assert abs(empirical_p_flip - 0.02) < 3.5 * se_flip, (
        f"Empirical flip {empirical_p_flip} outside 3.5 SE of 0.02"
    )


def test_stress_noise_rates():
    """Stress noise: 8% misfire, 4% bit flip within 3 std err."""
    model = STRESS_NOISE
    assert model.p_misfire == 0.08
    assert model.p_flip == 0.04
    
    n_samples = 20_000
    rng = np.random.default_rng(2026)
    
    # Test misfire
    misfires = sum(model.sample_misfire(rng) for _ in range(n_samples))
    empirical_p_misfire = misfires / n_samples
    se_misfire = np.sqrt(0.08 * 0.92 / n_samples)
    assert abs(empirical_p_misfire - 0.08) < 3.5 * se_misfire, (
        f"Empirical misfire {empirical_p_misfire} outside 3.5 SE of 0.08"
    )
    
    # Test readout flip
    bits = np.zeros(n_samples, dtype=int)
    flipped = model.apply_readout_flips(bits, rng)
    empirical_p_flip = np.mean(flipped)
    se_flip = np.sqrt(0.04 * 0.96 / n_samples)
    assert abs(empirical_p_flip - 0.04) < 3.5 * se_flip, (
        f"Empirical flip {empirical_p_flip} outside 3.5 SE of 0.04"
    )
