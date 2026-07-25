# Equations

This document records the symbolic model used by the MVP. The final calibrated
parameter values will come from the data pipeline and retrieval layer.

## State Variables

For each region $r$:

- $S_r(t)$: susceptible population
- $E_r(t)$: exposed population
- $I_r(t)$: affected / outpatient population
- $H_r(t)$: hospitalized population
- $R_r(t)$: recovered population
- $X_r(t)$: fossil dependency / pollution intensity state

## Coupled Dynamics

The exact parameter values are not fixed in this document. The solver will use
data-derived coefficients estimated from the source records.

$$
\frac{dS_r}{dt} = -\beta_r(X_r) S_r - \sum_{j} \Psi_{jr} S_r + \omega_r R_r
$$

$$
\frac{dE_r}{dt} = \beta_r(X_r) S_r - \sigma_r E_r + \sum_{j} \Psi_{jr} S_r
$$

$$
\frac{dI_r}{dt} = \sigma_r E_r - \gamma_r I_r - \eta_r I_r
$$

$$
\frac{dH_r}{dt} = \eta_r I_r - \rho_r H_r
$$

$$
\frac{dR_r}{dt} = \gamma_r I_r + \rho_r H_r - \omega_r R_r
$$

$$
\frac{dX_r}{dt} = -\kappa_r X_r - \lambda_r H_r + \sum_{j} \Phi_{jr} X_j
$$

## Interpretation

- Higher $X_r$ increases the exposure pressure $\beta_r(X_r)$.
- Higher hospitalization $H_r$ feeds back into policy pressure and reduces $X_r$.
- $\Psi_{jr}$ captures transboundary population or exposure coupling terms.
- $\Phi_{jr}$ captures transboundary pollution transport between regions.

The final implementation will define the data-driven form of $\beta_r(X_r)$ and
the lag structure for $\Psi_{jr}$ and $\Phi_{jr}$ from the source records.
