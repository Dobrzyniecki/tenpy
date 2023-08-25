"""Bosonic and fermionic Hubbard models."""
# Copyright 2019-2023 TeNPy Developers, GNU GPLv3

import numpy as np

from .model import CouplingMPOModel, NearestNeighborModel
from .lattice import Chain
from ..tools.params import asConfig
from ..networks.site import FermionSite, BosonSite, SpinHalfFermionSite, spin_half_species, DipolarBosonSite

__all__ = ['BoseHubbardModel', 'BoseHubbardChain', 'FermiHubbardModel', 'FermiHubbardChain',
           'FermiHubbardModel2', 'DipolarBoseHubbardChain']


class BoseHubbardModel(CouplingMPOModel):
    r"""Spinless Bose-Hubbard model.

    The Hamiltonian is:

    .. math ::
        H = - t \sum_{\langle i, j \rangle, i < j} (b_i^{\dagger} b_j + b_j^{\dagger} b_i)
            + V \sum_{\langle i, j \rangle, i < j} n_i n_j
            + \frac{U}{2} \sum_i n_i (n_i - 1) - \mu \sum_i n_i

    Here, :math:`\langle i,j \rangle, i< j` denotes nearest neighbor pairs.
    All parameters are collected in a single dictionary `model_params`, which
    is turned into a :class:`~tenpy.tools.params.Config` object.

    Parameters
    ----------
    model_params : :class:`~tenpy.tools.params.Config`
        Parameters for the model. See :cfg:config:`BoseHubbardModel` below.

    Options
    -------
    .. cfg:config :: BoseHubbardModel
        :include: CouplingMPOModel

        n_max : int
            Maximum number of bosons per site.
        filling : float
            Average filling.
        conserve: {'best' | 'N' | 'parity' | None}
            What should be conserved. See :class:`~tenpy.networks.Site.BosonSite`.
        t, U, V, mu: float | array
            Couplings as defined in the Hamiltonian above. Note the signs!
        phi_ext : float
            For 2D lattices and periodic y boundary conditions only.
            External magnetic flux 'threaded' through the cylinder. Hopping amplitudes for bonds
            'across' the periodic boundary are modified such that particles hopping around the
            circumference of the cylinder acquire a phase ``2 pi phi_ext``.
    """
    def init_sites(self, model_params):
        n_max = model_params.get('n_max', 3)
        filling = model_params.get('filling', 0.5)
        conserve = model_params.get('conserve', 'N')
        if conserve == 'best':
            conserve = 'N'
            self.logger.info("%s: set conserve to %s", self.name, conserve)
        site = BosonSite(Nmax=n_max, conserve=conserve, filling=filling)
        return site

    def init_terms(self, model_params):
        # 0) Read and set parameters.
        t = model_params.get('t', 1.)
        U = model_params.get('U', 0.)
        V = model_params.get('V', 0.)
        mu = model_params.get('mu', 0)
        phi_ext = model_params.get('phi_ext', None)
        for u in range(len(self.lat.unit_cell)):
            self.add_onsite(-mu - U / 2., u, 'N')
            self.add_onsite(U / 2., u, 'NN')
        for u1, u2, dx in self.lat.pairs['nearest_neighbors']:
            if phi_ext is None:
                hop = -t
            else:
                hop = self.coupling_strength_add_ext_flux(-t, dx, [0, 2 * np.pi * phi_ext])
            self.add_coupling(hop, u1, 'Bd', u2, 'B', dx, plus_hc=True)
            self.add_coupling(V, u1, 'N', u2, 'N', dx)


class BoseHubbardChain(BoseHubbardModel, NearestNeighborModel):
    """The :class:`BoseHubbardModel` on a Chain, suitable for TEBD.

    See the :class:`BoseHubbardModel` for the documentation of parameters.
    """
    def __init__(self, model_params):
        model_params = asConfig(model_params, self.__class__.__name__)
        model_params.setdefault('lattice', "Chain")
        CouplingMPOModel.__init__(self, model_params)


class FermiHubbardModel(CouplingMPOModel):
    r"""Spin-1/2 Fermi-Hubbard model.

    The Hamiltonian reads:

    .. math ::
        H = - \sum_{\langle i, j \rangle, i < j, \sigma} t (c^{\dagger}_{\sigma, i} c_{\sigma j} + h.c.)
            + \sum_i U n_{\uparrow, i} n_{\downarrow, i}
            - \sum_i \mu ( n_{\uparrow, i} + n_{\downarrow, i} )
            +  \sum_{\langle i, j \rangle, i< j, \sigma} V
                       (n_{\uparrow,i} + n_{\downarrow,i})(n_{\uparrow,j} + n_{\downarrow,j})


    Here, :math:`\langle i,j \rangle, i< j` denotes nearest neighbor pairs.
    All parameters are collected in a single dictionary `model_params`, which
    is turned into a :class:`~tenpy.tools.params.Config` object.

    .. warning ::
        Using the Jordan-Wigner string (``JW``) is crucial to get correct results!
        See :doc:`/intro/JordanWigner` for details.

    Parameters
    ----------
    model_params : :class:`~tenpy.tools.params.Config`
        Parameters for the model. See :cfg:config:`FermiHubbardModel` below.

    Options
    -------
    .. cfg:config :: FermiHubbardModel
        :include: CouplingMPOModel

        cons_N : {'N' | 'parity' | None}
            Whether particle number is conserved,
            see :class:`~tenpy.networks.site.SpinHalfFermionSite` for details.
        cons_Sz : {'Sz' | 'parity' | None}
            Whether spin is conserved,
            see :class:`~tenpy.networks.site.SpinHalfFermionSite` for details.
        t, U, mu : float | array
            Couplings as defined for the Hamiltonian above. Note the signs!
        phi_ext : float
            For 2D lattices and periodic y boundary conditions only.
            External magnetic flux 'threaded' through the cylinder. Hopping amplitudes for bonds
            'across' the periodic boundary are modified such that particles hopping around the
            circumference of the cylinder acquire a phase ``2 pi phi_ext``.
    """
    def init_sites(self, model_params):
        cons_N = model_params.get('cons_N', 'N')
        cons_Sz = model_params.get('cons_Sz', 'Sz')
        site = SpinHalfFermionSite(cons_N=cons_N, cons_Sz=cons_Sz)
        return site

    def init_terms(self, model_params):
        # 0) Read out/set default parameters.
        t = model_params.get('t', 1.)
        U = model_params.get('U', 0)
        V = model_params.get('V', 0)
        mu = model_params.get('mu', 0.)
        phi_ext = model_params.get('phi_ext', None)

        for u in range(len(self.lat.unit_cell)):
            self.add_onsite(-mu, u, 'Ntot')
            self.add_onsite(U, u, 'NuNd')
        for u1, u2, dx in self.lat.pairs['nearest_neighbors']:
            if phi_ext is None:
                hop = -t
            else:
                hop = self.coupling_strength_add_ext_flux(-t, dx, [0, 2 * np.pi * phi_ext])
            self.add_coupling(hop, u1, 'Cdu', u2, 'Cu', dx, plus_hc=True)
            self.add_coupling(hop, u1, 'Cdd', u2, 'Cd', dx, plus_hc=True)
            self.add_coupling(V, u1, 'Ntot', u2, 'Ntot', dx)


class FermiHubbardChain(FermiHubbardModel, NearestNeighborModel):
    """The :class:`FermiHubbardModel` on a Chain, suitable for TEBD.

    See the :class:`FermiHubbardModel` for the documentation of parameters.
    """
    default_lattice = Chain
    force_default_lattice = True


class FermiHubbardModel2(CouplingMPOModel):
    """Another implementation of the :class:`FermiHubbardModel`, but with local dimension 2.

    This class implements the same Hamiltonian as :class:`FermiHubbardModel`:


    However, it does not use the :class:`~tenpy.networks.site.SpinHalfFermionSite`, but two plain
    :class:`~tenpy.networks.site.FermionSite` for individual spin-up/down fermions, combined in the
    :class:`~tenpy.models.lattice.MultiSpeciesLattice`.

    Formally, not grouping the Sites leads to a better scaling of DMRG;
    yet, it can sometimes lead to ergodicity issues in practice.
    When you :meth:`group_sites` in this model, you will end up with the same MPO as the
    :class:`FermiHubbardModel`.


    .. warning ::
        Using the Jordan-Wigner string (``JW``) is crucial to get correct results!
        See :doc:`/intro/JordanWigner` for details.

    Options
    -------
    .. cfg:config :: FermiHubbardModel2
        include: FermiHubbardModel

    """

    def init_sites(self, model_params):
        cons_N = model_params.get('cons_N', 'N')
        cons_Sz = model_params.get('cons_Sz', 'Sz')
        return spin_half_species(FermionSite, cons_N=cons_N, cons_Sz=cons_Sz)
        # special syntax: returns tuple (sites, species_names) to cause
        # CouplingMPOModel.init_lattice to initialize a MultiSpeciesLattice
        # based on the lattice specified in the model parameters

    def init_terms(self, model_params):
        t = model_params.get('t', 1.)
        U = model_params.get('U', 0)
        V = model_params.get('V', 0)
        mu = model_params.get('mu', 0.)
        phi_ext = model_params.get('phi_ext', None)

        for u in range(len(self.lat.unit_cell)):
            self.add_onsite(-mu, u, 'N')
        for u1, u2, dx in self.lat.pairs['onsite_up-down']:
            self.add_coupling(U, u1, 'N', u2, 'N', dx)

        for u1, u2, dx in self.lat.pairs['nearest_neighbors_diag']:
            if phi_ext is None:
                hop = -t
            else:
                hop = self.coupling_strength_add_ext_flux(-t, dx, [0, 2 * np.pi * phi_ext])
            self.add_coupling(hop, u1, 'Cd', u2, 'C', dx, plus_hc=True)

        for u1, u2, dx in self.lat.pairs['nearest_neighbors_all-all']:
            self.add_coupling(V, u1, 'N', u2, 'N', dx)


class DipolarBoseHubbardChain(CouplingMPOModel):
    """Dipolar Bose-Hubbard model with and without explicit dipole conservation"""

    def init_lattice(self, model_params):
        """Initialize a 1D lattice"""
        L = model_params.get('L', 64)
        Nmax = model_params.get('Nmax', 2)
        cons_N = model_params.get('cons_N', True)
        cons_P = model_params.get('cons_P',  True)
        bc_MPS = model_params.get('bc_MPS', 'finite')
        bc = 'periodic' if bc_MPS in ['infinite', 'segment'] else 'open'
        bc = model_params.get('bc', bc)
        return Chain(L, DipolarBosonSite(Nmax=Nmax, conserve_N=cons_N, conserve_P=cons_P), bc=bc, bc_MPS=bc_MPS)

    def init_terms(self, model_params):
        """Add the onsite and coupling terms to the model"""
        L = model_params.get('L', 64)
        U = model_params.get('U', 1)
        t = model_params.get('t', 1)
        t_4 = model_params.get('t_4', 0)
        mu = model_params.get('mu', 0)

        # dipole hopping
        self.add_multi_coupling(-t, [('Bd', 0, 0), ('B', 1, 0), ('B', 1, 0), ('Bd', 2, 0)], plus_hc=True)
        self.add_multi_coupling(-t_4, [('Bd', 0, 0), ('B', 1, 0), ('B', 2, 0), ('Bd', 3, 0)], plus_hc=True)

        # on-site interactions and chemical potential
        self.add_onsite(U/2., 0, 'NN')
        self.add_onsite(-mu-U/2., 0, 'N')
