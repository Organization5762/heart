from heart.peripheral.providers.randomness import RandomnessProvider


class TestRandomnessProvider:
    """Validate shared randomness construction so providers can depend on one explicit seeded source."""

    def test_rng_reuses_project_seed_without_namespace(self) -> None:
        """Verify the default RNG path stays unnamespaced and deterministic so providers can share one project seed directly."""
        randomness = RandomnessProvider(seed=42)

        first = randomness.rng()
        second = randomness.rng()

        assert first.randint(0, 10_000) == second.randint(0, 10_000)

    def test_rng_supports_opt_in_namespacing(self) -> None:
        """Verify namespacing remains available when requested so callers can intentionally separate deterministic streams."""
        randomness = RandomnessProvider(seed=42)

        first = randomness.rng("alpha")
        second = randomness.rng("beta")

        assert first.randint(0, 10_000) != second.randint(0, 10_000)

    def test_numpy_rng_reuses_shared_seed(self) -> None:
        """Verify NumPy generators remain deterministic from the shared seed so simulation providers can reproduce state transitions."""
        randomness = RandomnessProvider(seed=42)

        first = randomness.numpy_rng()
        second = randomness.numpy_rng()

        assert first.integers(0, 10_000) == second.integers(0, 10_000)
