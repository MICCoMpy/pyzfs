from time import time
import numpy as np
import pkg_resources
import os
import psutil
from mpi4py import MPI
from lxml import etree

from ..common.parallel import ProcessorGrid, SymmetricDistributedMatrix
from ..common.cell import Cell
from ..common.ft import FourierTransform
from ..common.io import indent
from ..common.counter import Counter
from .ddi import compute_ddig
from .prefactor import prefactor
from .rhog import compute_rhog


class ZFSCalculation:
    """Zero field splitting D tensor calculation.

    Generally, calculation of D tensor involves pairwise iteration over many wavefuctions
    (KS orbitals). Physically, wavefunction is uniquely labeled by a 2-tuple of band index (int)
    and spin ("up" or "down"). Internally, each wavefunction is labeled by an integer index.
    Several maps are defined to describe related transformations.

    Attributes:
        wfc (Wavefunction): container for all KS orbitals
        cell (Cell): defines cell size, R and G vectors
        ft (FourierTransform): defines grid size for fourier transform

        ddig (ndarray): dipole-dipole interaction tensor in G space. Shape = (6, n1, n2, n3),
            where first index labels cartisian directions (xx, xy, xz, yy, yz, zz), last 3
            indices iterate over G space

        Iglobal (ndarray): global I array of shape (norbs, norbs, 6)
            first two indices iterate over wavefunctions, last index labels catesian directions
            in xx, xy, xz, yy, yz, xz manner
        I (ndarray): local I matrix, first two dimensions are distributed among processors
        D (ndarray): 3 by 3 matrix, total D tensor
        ev, evc (ndarray): eigenvalues and eigenvectors of D tensor
        Dvalue, Evalue (float): scalar D and E parameters for triplet

    """

    @indent(2)
    def __init__(self, wfcloader, memory="critical", comm=MPI.COMM_WORLD, **kwargs):
        """Initialize ZFS calculation.

        Args:
            wfcloader (WavefunctionLoader): defines how
            comm (MPI.comm): MPI communicator on which ZFS calculation will be distributed.
            memory (str): memory mode. Supported values:
                "high": high memory usage, better performance
                "low": low memory usage, some intermediate quantities will not be stored and
                    will be computed every time when needed
                "critical": lowest memory usage, some intermediate quantities will not be stored
                    and will be computed every time when needed
        """

        # Initialize control parameters
        self.memory = memory
        assert self.memory in ["high", "low", "critical"]

        # Define a 2D processor grid to parallelize summation over pairs of orbitals.
        self.pgrid = ProcessorGrid(comm, square=True)
        if self.pgrid.onroot:
            print("\n\nZero Field Splitting Calculation Created...\n\n")
        self.pgrid.print_info()

        # Parse wavefunctions, define cell and ft
        self.wfcloader = wfcloader

        self.wfc = self.wfcloader.wfc
        self.cell, self.ft = self.wfc.cell, self.wfc.ft

        # Declare ddig, I arrays and D arrays
        self.ddig = None

        if self.pgrid.onroot:
            print("\nCreating I array...\n")
        self.I = SymmetricDistributedMatrix(
            self.pgrid, (self.wfc.norbs, self.wfc.norbs, 6), np.float_
        )
        self.I.print_info("I")
        self.Iglobal = None

        self.D = np.zeros((3, 3))
        self.ev = np.zeros(3)
        self.evc = np.zeros((3, 3))
        self.Dvalue = 0
        self.Evalue = 0

        self.print_memory_usage()

    @indent(2)
    def solve(self):
        """Compute and gather local block of I in each processor."""
        self.pgrid.comm.barrier()
        t0 = time()

        # Load wavefunctions from files
        iorbs = set(
            list(range(self.I.mstart, self.I.mend))
            + list(range(self.I.nstart, self.I.nend))
        )
        self.wfcloader.load(iorbs=iorbs, sdm=self.I)
        del self.wfcloader
        self.pgrid.comm.barrier()
        self.print_memory_usage()
        t1 = time()

        if self.pgrid.onroot:
            print("Time elapsed for loading wfc: {:.0f}s".format(t1 - t0))

        # Compute dipole-dipole interaction tensor. Due to symmetry we only need the
        # upper triangular part of ddig
        if self.pgrid.onroot:
            print("\nComputing dipole-dipole interaction tensor in G space...\n")
        ddig = compute_ddig(self.cell, self.ft)
        self.ddig = ddig[np.triu_indices(3)]
        self.print_memory_usage()

        # Compute contribution to D tensor from every pair of electrons
        self.pgrid.comm.barrier()
        if self.pgrid.onroot:
            print("\nIterating over pairs...\n")
        wfc = self.wfc

        c = Counter(len(list(self.I.get_triu_iterator())), percent=0.01,
                    message="(process 0) {n} pairs ({percent}%) computed in {dt}...")

        for iloc, jloc in self.I.get_triu_iterator():
            # Load two wavefunctions
            i, j = self.I.ltog(iloc, jloc)
            if i == j:
                c.count()
                continue  # skip diagonal terms
            if wfc.iorb_sb_map[i][0] == wfc.iorb_sb_map[j][0]:
                chi = 1
            else:
                chi = -1

            psi1r = wfc.get_psir(i)
            psi2r = wfc.get_psir(j)
            rho1g = wfc.get_rhog(i)
            rho2g = wfc.get_rhog(j)

            try:
                import cupy as cp
                rhog_d = compute_rhog(psi1r, psi2r, self.ft, rho1g=rho1g, rho2g=rho2g)
                rhog = cp.asnumpy(rhog_d)
            except ImportError:
                rhog = compute_rhog(psi1r, psi2r, self.ft, rho1g=rho1g, rho2g=rho2g)

            # Factor to be multiplied with I:
            #   chi comes from spin direction
            #   prefactor comes from physical constants and unit conversions
            #   omega**2 comes from convention of FT used here
            fac = chi * prefactor * self.cell.omega ** 2

            self.I[iloc, jloc, ...] = np.real(fac * np.tensordot(self.ddig, rhog, axes=3))
            # TODO: check if it is safe to only use real apart
            c.count()

        self.I.symmetrize()

        # All processor sync local matrix to get global matrix
        self.Iglobal = self.I.collect()

        # Sum over G vectors to get D tensor
        self.D[np.triu_indices(3)] = np.sum(self.Iglobal, axis=(0, 1))
        self.D = self.D + self.D.T - np.diag(self.D.diagonal())
        self.ev, self.evc = np.linalg.eig(self.D)

        # For triplet states, compute D and E parameters:
        # Denote three eigenvalues as Dx, Dy, Dz: |Dz| > |Dx| > |Dy|
        # D = 3/2 Dz, E = 1/2(Dx - Dy)
        args = np.abs(self.ev).argsort()
        dy, dx, dz = self.ev[args]
        self.Dvalue = 1.5 * dz
        self.Evalue = 0.5 * (dx - dy)

        if self.pgrid.onroot:
            print("\n\nTotal D tensor (MHz): ")
            print(self.D)
            print("D eigenvalues (MHz): ")
            print(self.ev)
            print("D eigenvectors: ")
            print(self.evc[:, 0])
            print(self.evc[:, 1])
            print(self.evc[:, 2])
            print("Dx, Dy, Dz (|Dz| > |Dx| > |Dy|) (MHz): ")
            print(dx, dy, dz)
            print("Scalar D = {:.2f} MHz, E = {:.2f} MHz".format(self.Dvalue, self.Evalue))
            print("Time elapsed for pair iteration: {:.0f}s".format(time() - t1))

    @indent(2)
    def print_memory_usage(self):
        pyproc = psutil.Process(os.getpid())
        memloc = np.array(pyproc.memory_info()[0]/2.**20, dtype="f")
        memtot = np.array(0.0, dtype="f")
        MPI.COMM_WORLD.Reduce([memloc, MPI.FLOAT], [memtot, MPI.FLOAT])

        if self.pgrid.onroot:
            print("\nMemory usage (on process 0):")

            for obj in ["iorb_psir_map", "iorb_rhog_map"]:
                try:
                    nbytes = np.sum(value.nbytes for value in self.wfc.__dict__[obj].values())
                    print("  {:10} {:.2f} MB".format(obj, nbytes/1024.**2))
                except KeyError:
                    pass

            for obj in ["ddig", "I", "Iglobal"]:
                try:
                    nbytes = self.__dict__[obj].nbytes
                    print("  {:10} {:.2f} MB".format(obj, nbytes/1024.**2))
                except AttributeError:
                    pass

            print("\nTotal memory usage (on process 0): {:.2f} MB".format(memloc))
            print("Total memory usage (all processes): {:.2f} MB".format(memtot))

    def get_xml(self):
        """Generate an xml to store information of this calculation.

        Returns:
            A string containing xml.

        """
        try:
            version = pkg_resources.require("PyZFS")[0].version
        except Exception:
            version = ""

        root = etree.Element("root")
        etree.SubElement(root, "code").text = "PyZFS"
        etree.SubElement(root, "version").text = version
        etree.SubElement(root, "object").text = self.__class__.__name__
        etree.SubElement(root, "DTensor", unit="MHz").text = np.array2string(self.D)
        etree.SubElement(root, "D", unit="MHz").text = "{:.2f}".format(self.Dvalue)
        etree.SubElement(root, "E", unit="MHz").text = "{:.2f}".format(self.Evalue)

        tree = etree.ElementTree(root)
        return etree.tostring(tree, pretty_print=True)
