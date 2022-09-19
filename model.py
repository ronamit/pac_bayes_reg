import torch
from torch import tensor
import torch.nn as nn
from utils import draw_uniformly_in_ball, to_device
from bounds import wpb_bound
from data import PairsDataset

def loss_func(h: tensor, X: tensor, y: tensor) -> tensor:
    assert h.n_dim == 1
    assert X.n_dim == 2  # [n_samp x d]
    assert y.n_dim == 1
    assert y.shape[0] == X.shape[0]
    return torch.square(torch.matmul(X, h) - y) / 4


class PacBayesLinReg(nn.Module):
    def __init__(self, d: int, r: float, mu_Q_max_radius: float, sigma_Q: float, mu_P: tensor, sigma_P: float):
        super().__init__()
        self.r = r
        self.mu_Q_max_radius = mu_Q_max_radius
        mu_Q_init = draw_uniformly_in_ball(d, mu_Q_max_radius).squeeze()
        self.mu_Q = nn.Parameter(mu_Q_init)
        self.sigma_Q = sigma_Q
        self.mu_P = mu_P
        self.sigma_P = sigma_P
        self.d = d

    def project_to_domain(self):
        with torch.no_grad():
            mu_norm_sqr = torch.sum(self.mu_Q ** 2)
            if mu_norm_sqr > self.r:
                self.mu_Q *= self.r / torch.sqrt(mu_norm_sqr)

    def empirical_risk(self, X: tensor, Y: tensor) -> tensor:
        n_samp = X.shape[0]
        return (torch.sum((X @ self.mu_Q - Y) ** 2) + self.sigma_Q ** 2 * torch.sum(X[:] ** 2)) / (4 * n_samp)

    def draw_from_posterior(self):
        eps = torch.randn_like(self.mu_Q)
        h = self.mu_Q + eps * self.sigma_Q
        return h

    def wpb_risk_bound(self, X: tensor, Y: tensor, delta: float) -> tensor:
        n_samp = X.shape[0]
        emp_risk = self.empirical_risk(X, Y)
        gap_bound = wpb_bound(n_samp, delta, self.mu_Q, self.sigma_Q,  self.mu_P, self.sigma_P, self.d, self.r)
        return emp_risk + gap_bound

    def run_evaluation(self, args, data_loader):
        self.eval()
        avg_loss = 0
        n_samp = len(data_loader.dataset)
        with torch.no_grad():
            for i, (X, Y) in enumerate(data_loader):
                to_device(args.device, X, Y)
                loss = self.wpb_risk_bound(X, Y, args.delta)
                avg_loss += loss.item()
        avg_loss /= n_samp
        return avg_loss
