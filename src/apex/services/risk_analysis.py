"""
Industrial-grade Monte Carlo risk analysis engine.

WARNING: Toy implementations are prohibited.
This module implements:
- Latin Hypercube Sampling (LHS) via scipy.stats.qmc
- Multiple distribution types (triangular, normal, uniform, lognormal, PERT)
- Optional Iman-Conover correlation for risk factor dependencies
- Spearman rank correlation sensitivity analysis

HIGH-RISK AREAS flagged for human review:
- _apply_iman_conover() must be validated against known tools (@RISK, Crystal Ball)
- _transform_samples() must be verified with test cases for all distributions
- PERT distribution uses triangular approximation (TODO: implement proper Beta distribution)

PROHIBITED PACKAGES:
- mcerp (outdated, NumPy incompatible) - use scipy.stats instead
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.stats import beta, lognorm, norm, qmc, rankdata, triang, uniform

from apex.utils.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


@dataclass
class RiskFactor:
    """
    Risk factor definition for Monte Carlo analysis.

    Distribution types:
    - triangular: Requires min, likely, max
    - normal: Requires mean, std_dev
    - uniform: Requires min, max
    - lognormal: Requires mean, std_dev
    - pert: Requires min, likely, max (PERT distribution)
    """

    name: str
    distribution: str  # "triangular", "normal", "uniform", "lognormal", "pert"
    min_value: Optional[float] = None
    most_likely: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None


class MonteCarloRiskAnalyzer:
    """
    Industrial-grade Monte Carlo simulation engine.

    Features:
    - Latin Hypercube Sampling for better convergence
    - Multiple probability distributions
    - Optional correlation via Iman-Conover method
    - Spearman rank correlation for sensitivity analysis
    """

    def __init__(self, iterations: int = 10000, random_seed: int = 42):
        """
        Initialize Monte Carlo analyzer.

        Args:
            iterations: Number of simulation iterations (default 10000)
            random_seed: Random seed for reproducibility
        """
        self.iterations = iterations
        self.random_seed = random_seed

    def run_analysis(
        self,
        base_cost: float,
        risk_factors: Dict[str, RiskFactor],
        correlation_matrix: Optional[np.ndarray] = None,
        confidence_levels: List[float] = [0.50, 0.80, 0.95],
    ) -> Dict[str, Any]:
        """
        Execute Monte Carlo risk analysis.

        Args:
            base_cost: Base cost estimate (pre-risk)
            risk_factors: Dictionary of risk factors
            correlation_matrix: Optional correlation matrix (n_vars x n_vars)
            confidence_levels: List of confidence levels for percentile calculation

        Returns:
            Dictionary with analysis results including percentiles and sensitivities

        Raises:
            BusinessRuleViolation: If correlation matrix is invalid
                (not symmetric, wrong size, etc.)
        """
        np.random.seed(self.random_seed)

        logger.info(
            f"Starting Monte Carlo analysis: base_cost=${base_cost:,.2f}, "
            f"{len(risk_factors)} risk factors, {self.iterations} iterations"
        )

        factor_names = list(risk_factors.keys())
        n_vars = len(factor_names)

        if n_vars == 0:
            # No risk factors - return base cost
            return {
                "base_cost": base_cost,
                "mean_cost": base_cost,
                "std_dev": 0.0,
                "percentiles": {f"p{int(level * 100)}": base_cost for level in confidence_levels},
                "min_cost": base_cost,
                "max_cost": base_cost,
                "iterations": self.iterations,
                "risk_factors_applied": [],
                "sensitivities": {},
            }

        # Latin Hypercube Sampling
        sampler = qmc.LatinHypercube(d=n_vars, seed=self.random_seed)
        lhs_samples = sampler.random(self.iterations)  # Shape: (iterations, n_vars)

        # Transform uniform samples to distribution-specific samples
        transformed = np.zeros_like(lhs_samples)
        for j, name in enumerate(factor_names):
            factor = risk_factors[name]
            transformed[:, j] = self._transform_samples(lhs_samples[:, j], factor)
            logger.debug(
                f"Transformed risk factor '{name}' using {factor.distribution} distribution"
            )

        # Apply correlation if matrix provided
        if correlation_matrix is not None:
            # Validate correlation matrix before using
            self._validate_correlation_matrix(correlation_matrix, n_vars)

            logger.warning(
                "Iman-Conover correlation applied - HIGH-RISK AREA requiring human validation"
            )
            transformed = self._apply_iman_conover(transformed, correlation_matrix)

        # Compute total cost multipliers (risk factors expressed as fractional impact)
        # e.g., +10% risk = 0.10, -5% risk = -0.05
        total_multipliers = 1.0 + transformed.sum(axis=1)
        risk_adjusted_costs = base_cost * total_multipliers

        # Compute percentiles
        percentiles = {}
        for level in confidence_levels:
            value = float(np.percentile(risk_adjusted_costs, level * 100))
            percentiles[f"p{int(level * 100)}"] = round(value, 2)

        mean_cost = float(np.mean(risk_adjusted_costs))
        std_dev = float(np.std(risk_adjusted_costs))

        # Spearman rank correlation for sensitivity analysis
        sensitivities = self._compute_spearman_sensitivity(
            transformed, risk_adjusted_costs, factor_names
        )

        return {
            "base_cost": base_cost,
            "mean_cost": round(mean_cost, 2),
            "std_dev": round(std_dev, 2),
            "percentiles": percentiles,
            "min_cost": round(float(np.min(risk_adjusted_costs)), 2),
            "max_cost": round(float(np.max(risk_adjusted_costs)), 2),
            "iterations": self.iterations,
            "risk_factors_applied": factor_names,
            "sensitivities": sensitivities,
        }

    def _validate_correlation_matrix(self, correlation_matrix: np.ndarray, n_vars: int) -> None:
        """
        Validate correlation matrix for validity.

        Args:
            correlation_matrix: Correlation matrix to validate
            n_vars: Expected number of variables

        Raises:
            BusinessRuleViolation: If matrix is invalid
        """
        # Check shape
        if correlation_matrix.shape != (n_vars, n_vars):
            raise BusinessRuleViolation(
                message=f"Correlation matrix shape {correlation_matrix.shape} doesn't match "
                f"{n_vars} risk factors (expected {n_vars}x{n_vars})",
                code="INVALID_CORRELATION_MATRIX_SHAPE",
            )

        # Check symmetry
        if not np.allclose(correlation_matrix, correlation_matrix.T):
            raise BusinessRuleViolation(
                message="Correlation matrix must be symmetric",
                code="CORRELATION_MATRIX_NOT_SYMMETRIC",
            )

        # Check diagonal is all 1s
        diagonal = np.diagonal(correlation_matrix)
        if not np.allclose(diagonal, 1.0):
            raise BusinessRuleViolation(
                message=f"Correlation matrix diagonal must be all 1.0, got {diagonal}",
                code="CORRELATION_MATRIX_INVALID_DIAGONAL",
            )

        # Check values in valid range [-1, 1]
        if not np.all((correlation_matrix >= -1.0) & (correlation_matrix <= 1.0)):
            raise BusinessRuleViolation(
                message="Correlation matrix values must be in range [-1, 1]",
                code="CORRELATION_MATRIX_OUT_OF_RANGE",
            )

        # Check positive semi-definite (will be checked again in Cholesky, but good to fail early)
        eigenvalues = np.linalg.eigvals(correlation_matrix)
        if np.any(eigenvalues < -1e-10):  # Small tolerance for numerical errors
            logger.warning(
                f"Correlation matrix has negative eigenvalues: {eigenvalues[eigenvalues < 0]}"
            )
            # Don't fail here - Cholesky will catch it and we'll fallback gracefully

    def _transform_samples(self, u: np.ndarray, factor: RiskFactor) -> np.ndarray:
        """
        Transform uniform [0,1] samples to distribution-specific samples.

        Returns cost impact multipliers (e.g., 0.1 for +10% impact).

        Args:
            u: Uniform [0,1] samples
            factor: Risk factor definition

        Returns:
            Transformed samples representing fractional cost impacts

        Raises:
            ValueError: If distribution type is unsupported or parameters invalid
        """
        dist = factor.distribution.lower()

        if dist == "triangular":
            if factor.min_value is None or factor.most_likely is None or factor.max_value is None:
                raise ValueError(
                    f"Triangular distribution requires min, likely, max: {factor.name}"
                )

            # Scipy triangular uses mode=(c-loc)/(scale) where loc=min, scale=max-min
            loc = factor.min_value
            scale = factor.max_value - factor.min_value
            c = (factor.most_likely - loc) / scale if scale > 0 else 0.5

            return triang.ppf(u, c=c, loc=loc, scale=scale)

        elif dist == "normal":
            if factor.mean is None or factor.std_dev is None:
                raise ValueError(f"Normal distribution requires mean, std_dev: {factor.name}")

            return norm.ppf(u, loc=factor.mean, scale=factor.std_dev)

        elif dist == "uniform":
            if factor.min_value is None or factor.max_value is None:
                raise ValueError(f"Uniform distribution requires min, max: {factor.name}")

            return uniform.ppf(u, loc=factor.min_value, scale=factor.max_value - factor.min_value)

        elif dist == "lognormal":
            if factor.mean is None or factor.std_dev is None:
                raise ValueError(f"Lognormal distribution requires mean, std_dev: {factor.name}")

            # Convert normal mean/std to lognormal parameters
            mean = factor.mean
            std = factor.std_dev

            mu = np.log(mean**2 / np.sqrt(mean**2 + std**2))
            sigma = np.sqrt(np.log(1 + (std**2 / mean**2)))

            return lognorm.ppf(u, s=sigma, scale=np.exp(mu))

        elif dist == "pert":
            # PERT distribution using Beta distribution
            # MEDIUM FIX: Proper PERT implementation using scipy.stats.beta
            # instead of triangular approximation
            if factor.min_value is None or factor.most_likely is None or factor.max_value is None:
                raise ValueError(f"PERT distribution requires min, likely, max: {factor.name}")

            # PERT distribution parameters
            # Uses Beta distribution scaled to [min, max] with mode at most_likely
            # Shape parameters: α = 1 + 4*(mode-min)/(max-min), β = 1 + 4*(max-mode)/(max-min)
            min_val = factor.min_value
            max_val = factor.max_value
            mode = factor.most_likely

            if max_val <= min_val:
                raise ValueError(f"PERT distribution requires max > min: {factor.name}")

            if not (min_val <= mode <= max_val):
                raise ValueError(f"PERT mode must be between min and max: {factor.name}")

            # Calculate Beta shape parameters for PERT
            # Lambda parameter (usually 4 for PERT, but can vary)
            lambda_pert = 4.0
            range_val = max_val - min_val

            if range_val > 0:
                alpha = 1.0 + lambda_pert * (mode - min_val) / range_val
                beta_param = 1.0 + lambda_pert * (max_val - mode) / range_val
            else:
                # Degenerate case - return mode
                return np.full_like(u, mode)

            # Sample from Beta(alpha, beta) and scale to [min, max]
            beta_samples = beta.ppf(u, alpha, beta_param)
            return min_val + beta_samples * range_val

        else:
            raise ValueError(f"Unsupported distribution type: {dist}")

    def _apply_iman_conover(
        self, samples: np.ndarray, correlation_matrix: np.ndarray
    ) -> np.ndarray:
        """
        Apply Iman-Conover method to induce correlation while preserving marginal distributions.

        HIGH-RISK FUNCTION: This implementation MUST be reviewed by a human
        and validated against known cases from trusted tools (e.g., @RISK, Crystal Ball)
        before being used in production.

        Algorithm:
        1. Rank-transform original samples
        2. Generate correlated normal scores using Cholesky decomposition
        3. Rank correlated normals
        4. Map correlated ranks back onto original sample distributions

        Args:
            samples: Original samples (iterations x n_vars)
            correlation_matrix: Correlation matrix (n_vars x n_vars)

        Returns:
            Correlated samples with preserved marginal distributions
        """
        n_samples, n_vars = samples.shape

        # Validate correlation matrix
        if correlation_matrix.shape != (n_vars, n_vars):
            msg = (
                f"Correlation matrix shape {correlation_matrix.shape} "
                f"doesn't match variables {n_vars}"
            )
            raise ValueError(msg)

        # 1. Rank-transform original samples
        ranked = np.apply_along_axis(rankdata, 0, samples)

        # 2. Generate correlated normal scores
        try:
            L = np.linalg.cholesky(correlation_matrix)
        except np.linalg.LinAlgError:
            logger.error("Correlation matrix is not positive definite - using original samples")
            return samples

        # Convert ranks to normal quantiles
        normals = norm.ppf((ranked - 0.5) / n_samples)

        # Apply correlation via Cholesky factor
        correlated = normals @ L.T

        # 3. Rank correlated normals
        correlated_ranks = np.apply_along_axis(rankdata, 0, correlated)

        # 4. Map correlated ranks back onto sorted original samples
        result = np.zeros_like(samples)
        for j in range(n_vars):
            # Sort original samples for this variable
            sorted_original = np.sort(samples[:, j])

            # Get permutation that would sort correlated ranks
            order = np.argsort(correlated_ranks[:, j])

            # Apply inverse permutation to sorted originals
            result[order, j] = sorted_original

        return result

    def _compute_spearman_sensitivity(
        self,
        factor_samples: np.ndarray,
        total_costs: np.ndarray,
        factor_names: List[str],
    ) -> Dict[str, float]:
        """
        Compute Spearman rank correlation coefficients for sensitivity analysis.

        Higher absolute correlation indicates greater influence on total cost.

        Args:
            factor_samples: Risk factor samples (iterations x n_vars)
            total_costs: Total cost outcomes (iterations,)
            factor_names: Names of risk factors

        Returns:
            Dictionary mapping factor names to Spearman correlation coefficients
        """
        sensitivities: Dict[str, float] = {}

        for j, name in enumerate(factor_names):
            # Rank both variables
            x_ranked = rankdata(factor_samples[:, j])
            y_ranked = rankdata(total_costs)

            # Compute Pearson correlation of ranks (= Spearman correlation)
            corr = np.corrcoef(x_ranked, y_ranked)[0, 1]

            sensitivities[name] = round(float(corr), 4)

        return sensitivities
