from __future__ import absolute_import, division, print_function
import numpy as np
from mpi4py import MPI

from .baseloader import WavefunctionLoader
from ..cell import Cell
from ..ft import FourierTransform
from .wavefunction import Wavefunction
from ..counter import Counter
from ..parallel import SymmetricDistributedMatrix

from ...common.misc import empty_ase_cell
from ..units import bohr_to_angstrom

from scipy.ndimage import zoom, _ni_support

from gpaw import GPAW
from gpaw.mpi import serial_comm
from gpaw.utilities.ps2ae import PS2AE


def _compute_offset(sdm, iorb):
    """compute the index for iorb^th wfc, note that some rows in psir_arrs_all
    are zero to facilitate MPI scatter"""
    nproc = iloc = 0
    for iproc in range(sdm.pgrid.nrow):
        mstart, mloc, mend, nstart, nloc, nend = sdm.indexmap[iproc, 0]
        if mstart > iorb:
            break
        nproc = iproc
        iloc = iorb - mstart
    return nproc * sdm.mlocx + iloc


class GPAWWavefunctionLoader(WavefunctionLoader):

    def __init__(self, gpwfile, ae=False, ae_reduce=4, comm=MPI.COMM_WORLD):
        self.gpwfile = gpwfile
        self.ae = ae
        self.ae_reduce = ae_reduce
        super(GPAWWavefunctionLoader, self).__init__()

    def scan(self):
        super(GPAWWavefunctionLoader, self).scan()

        # Load GPAW calculator
        self.calc_gpaw = GPAW(
            self.gpwfile,
            communicator=serial_comm,
        )
        self.calc_gpaw_ps2ae = PS2AE(self.calc_gpaw)

        # Parse cell
        cell = Cell(
            empty_ase_cell(*self.calc_gpaw.atoms.get_cell().array.T, unit="angstrom")
        )

        # Create FT objects
        # Note dimensions of reduced WF
        # (https://github.com/scipy/scipy/blob/v1.17.0/scipy/ndimage/_interpolation.py#L763-L894)
        if self.ae:
            self.ae_reduce_arr = _ni_support._normalize_sequence(
                1.0 / self.ae_reduce, 3
            )
            self.realgrid = np.array(
                [
                    int(round(ii * jj))
                    for ii, jj in zip(self.calc_gpaw_ps2ae.gd.N_c, self.ae_reduce_arr)
                ]
            )
        else:
            self.realgrid = self.calc_gpaw.wfs.gd.N_c
        self.wft = FourierTransform(
            self.realgrid[0], self.realgrid[1], self.realgrid[2]
        )
        self.dft = FourierTransform(
            self.realgrid[0], self.realgrid[1], self.realgrid[2]
        )

        # Spin / k-point sanity checks
        assert self.calc_gpaw.get_number_of_spins() == 2
        assert len(self.calc_gpaw.wfs.kpt_u) == 2  # up, down
        for kpt in self.calc_gpaw.wfs.kpt_u:
            assert kpt.k == 0.0  # Gamma only
        self.gamma = True

        # Occupied orbitals
        occs = [kpt.f_n for kpt in self.calc_gpaw.wfs.kpt_u]
        iuorbs = np.where(occs[0] > 0.8)[0]
        idorbs = np.where(occs[1] > 0.8)[0]

        nuorbs = len(iuorbs)
        ndorbs = len(idorbs)
        norbs = nuorbs + ndorbs

        iorb_sb_map = list(
            ("up", iuorbs[iwfc]) if iwfc < nuorbs else ("down", idorbs[iwfc - nuorbs])
            for iwfc in range(norbs)
        )
        # GPAW does not use files
        iorb_fname_map = ["None"] * norbs

        self.wfc = Wavefunction(
            cell=cell,
            ft=self.wft,
            nuorbs=nuorbs,
            ndorbs=ndorbs,
            iorb_sb_map=iorb_sb_map,
            iorb_fname_map=iorb_fname_map,
            dft=self.dft,
            gamma=self.gamma,
        )

    def load(self, iorbs, sdm):
        super(GPAWWavefunctionLoader, self).load(iorbs, sdm)
        assert isinstance(sdm, SymmetricDistributedMatrix)
        comm = sdm.comm
        rank = sdm.pgrid.rank
        onroot = sdm.onroot

        if self.ae:

            # processor 0 parse wavefunctions
            psir_all = None
            arr_len = np.prod(self.realgrid)
            if onroot:
                psir_all = np.zeros([sdm.mx, arr_len], dtype=np.complex128)
                c = Counter(
                    self.wfc.norbs,
                    percent=0.1,
                    message="(process 0) {n} orbitals ({percent}%) loaded in {dt}...",
                )

                nbands = self.calc_gpaw.get_number_of_bands()
                for ispin in range(2):
                    for iband in range(nbands):

                        # Get all-electron (PAW-reconstructed) wavefunctions
                        psir_ae = self.calc_gpaw_ps2ae.get_wave_function(
                            n=iband, s=ispin, ae=self.ae
                        )

                        # Linearly interpolate
                        psir = zoom(psir_ae, self.ae_reduce_arr, order=1)

                        # Convert from 1/Angstrom^(3/2) to 1/bohr^(3/2)
                        psir *= bohr_to_angstrom ** (3.0 / 2)

                        psir = self.wfc.normalize(psir)

                        iorb = self.wfc.sb_iorb_map.get(
                            ("up" if ispin == 0 else "down", iband)
                        )
                        if iorb is not None:
                            offset = _compute_offset(sdm, iorb)
                            psir_all[offset] = psir.flatten()
                            c.count()

            # scatter wavefunctions
            # allocate wfc arrays
            psir_m = np.zeros([sdm.mlocx, arr_len], dtype=np.complex128)
            psir_n = np.zeros([sdm.nlocx, arr_len], dtype=np.complex128)
            comm.barrier()

            # root -> first column scatter
            if onroot:
                print("GPAWWavefunctionLoader: root -> first column scattering")
            if sdm.icol == 0:
                sdm.colcomm.Scatter(sendbuf=psir_all, recvbuf=psir_m, root=0)
            comm.barrier()

            # first column -> other column bcast
            if onroot:
                print("GPAWWavefunctionLoader: first column -> other column bcast")
            sdm.rowcomm.Bcast(psir_m, root=0)
            comm.barrier()

            # root -> first row scatter
            if onroot:
                print("GPAWWavefunctionLoader: root -> first row scattering")
            if sdm.irow == 0:
                sdm.rowcomm.Scatter(sendbuf=psir_all, recvbuf=psir_n, root=0)
            comm.barrier()

            # first row -> other row bcast
            if onroot:
                print("GPAWWavefunctionLoader: first row -> other row bcast")
            sdm.colcomm.Bcast(psir_n, root=0)
            comm.barrier()

            if onroot:
                del psir_all

            for iloc in range(sdm.mloc):
                iorb = sdm.ltog(iloc)
                self.wfc.set_psir(iorb, psir_m[iloc].reshape(*self.realgrid))

            for iloc in range(sdm.nloc):
                iorb = sdm.ltog(0, iloc)[1]
                try:
                    self.wfc.set_psir(iorb, psir_n[iloc].reshape(*self.realgrid))
                except ValueError:
                    pass

        else:

            for iloc in range(sdm.mloc):
                iorb = sdm.ltog(iloc)

                # Get orbital info
                spin = self.wfc.iorb_sb_map[iorb][0]
                if spin == "up":
                    ispin = 0
                elif spin == "down":
                    ispin = 1
                iband = self.wfc.iorb_sb_map[iorb][1]

                # Get pseudo WF
                psir = self.calc_gpaw.get_pseudo_wave_function(band=iband, spin=ispin)

                # Convert from 1/Angstrom^(3/2) to 1/bohr^(3/2)
                psir *= bohr_to_angstrom ** (3.0 / 2)

                psir = self.wfc.normalize(psir)

                self.wfc.set_psir(iorb, psir)

            for iloc in range(sdm.nloc):
                iorb = sdm.ltog(0, iloc)[1]

                # Get orbital info
                spin = self.wfc.iorb_sb_map[iorb][0]
                if spin == "up":
                    ispin = 0
                elif spin == "down":
                    ispin = 1
                iband = self.wfc.iorb_sb_map[iorb][1]

                # Get pseudo WF
                psir = self.calc_gpaw.get_pseudo_wave_function(band=iband, spin=ispin)

                # Convert from 1/Angstrom^(3/2) to 1/bohr^(3/2)
                psir *= bohr_to_angstrom ** (3.0 / 2)

                psir = self.wfc.normalize(psir)

                try:
                    self.wfc.set_psir(iorb, psir)
                except ValueError:
                    pass

        comm.barrier()

        if self.memory == "high":
            self.wfc.compute_all_rhog()
        elif self.memory == "low" or self.memory == "critical":
            pass
        else:
            raise ValueError
