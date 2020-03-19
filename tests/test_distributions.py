import pytest
import torch as th

from torchy_baselines import A2C, PPO
from torchy_baselines.common.distributions import (DiagGaussianDistribution, TanhBijector,
                                                   StateDependentNoiseDistribution,
                                                   CategoricalDistribution)
from torchy_baselines.common.utils import set_random_seed


N_ACTIONS = 2
N_FEATURES = 3
N_SAMPLES = int(5e6)


def test_bijector():
    """
    Test TanhBijector
    """
    actions = th.ones(5) * 2.0
    bijector = TanhBijector()

    squashed_actions = bijector.forward(actions)
    # Check that the boundaries are not violated
    assert th.max(th.abs(squashed_actions)) <= 1.0
    # Check the inverse method
    assert th.isclose(TanhBijector.inverse(squashed_actions), actions).all()


@pytest.mark.parametrize("model_class", [A2C, PPO])
def test_squashed_gaussian(model_class):
    """
    Test run with squashed Gaussian (notably entropy computation)
    """
    model = model_class('MlpPolicy', 'Pendulum-v0', use_sde=True, n_steps=100, policy_kwargs=dict(squash_output=True))
    model.learn(500)


def test_sde_distribution():
    n_actions = 1
    deterministic_actions = th.ones(N_SAMPLES, n_actions) * 0.1
    state = th.ones(N_SAMPLES, N_FEATURES) * 0.3
    dist = StateDependentNoiseDistribution(n_actions, full_std=True, squash_output=False)

    set_random_seed(1)
    _, log_std = dist.proba_distribution_net(N_FEATURES)
    dist.sample_weights(log_std, batch_size=N_SAMPLES)

    actions, _ = dist.proba_distribution(deterministic_actions, log_std, state)

    assert th.allclose(actions.mean(), dist.distribution.mean.mean(), rtol=1e-3)
    assert th.allclose(actions.std(), dist.distribution.scale.mean(), rtol=1e-3)


# TODO: analytical form for squashed Gaussian?
@pytest.mark.parametrize("dist", [
    DiagGaussianDistribution(N_ACTIONS),
    StateDependentNoiseDistribution(N_ACTIONS, squash_output=False),
])
def test_entropy(dist):
    # The entropy can be approximated by averaging the negative log likelihood
    # mean negative log likelihood == differential entropy
    set_random_seed(1)
    state = th.rand(N_SAMPLES, N_FEATURES)
    deterministic_actions = th.rand(N_SAMPLES, N_ACTIONS)
    _, log_std = dist.proba_distribution_net(N_FEATURES, log_std_init=th.log(th.tensor(0.2)))

    if isinstance(dist, DiagGaussianDistribution):
        actions, dist = dist.proba_distribution(deterministic_actions, log_std)
    else:
        dist.sample_weights(log_std, batch_size=N_SAMPLES)
        actions, dist = dist.proba_distribution(deterministic_actions, log_std, state)

    entropy = dist.entropy()
    log_prob = dist.log_prob(actions)
    assert th.allclose(entropy.mean(), -log_prob.mean(), rtol=5e-3)


def test_categorical():
    # The entropy can be approximated by averaging the negative log likelihood
    # mean negative log likelihood == entropy
    dist = CategoricalDistribution(N_ACTIONS)
    set_random_seed(1)
    state = th.rand(N_SAMPLES, N_FEATURES)
    action_logits = th.rand(N_SAMPLES, N_ACTIONS)
    actions, dist = dist.proba_distribution(action_logits)

    entropy = dist.entropy()
    log_prob = dist.log_prob(actions)
    assert th.allclose(entropy.mean(), -log_prob.mean(), rtol=1e-4)
