from .FileParser import FileParser
from ..base.Molecule import Molecule
from ..base.Atom import Atom
import pandas as pd
import numpy as np
from typing import List

class OrcaOut (FileParser):

    """A file parser for ORCA standard output files"""
    extension = "out"

    def read_scalar_data(self):
        """Method to read basic properties from ORCA output.
        ARGS:
            NONE
        RETURNS:
            (dict) dictionary with properties
                    {
                        "runtime": (float) runtime in seconds,
                        "final_energy": (float) final energy in Hartree,
                        "finished_normally": (bool) wheather computation finished without errors
                        "homo_ev": (float) the energy of the HOMO level in eV,
                        "lumo_ev":(float) the energy of the LUMO level in eV,
                        "has_imaginary_freq": (bool) if the molecule has imaginary frequencies (if no frequency calculation done, returns NONE)
                        "gibbs_free_energy": (float) value of gibbs free energy of the molecule (if no frequency calculation done, returns NONE)
                    }"""
        outdict = {
            "runtime": None,
            "final_energy": None,
            "finished_normally": False,
            "n_electrons": None,
            "homo_ev": None,
            "lumo_ev": None,
            "has_imaginary_freq": None,
            "gibbs_free_energy": None
        }
        MoEnergyBlock = False
        FreqCalc = False
        HasImFreq = False
        with open(self.path, "r", encoding="utf8") as f:
            for line in f.readlines():
                if "FINAL SINGLE POINT ENERGY" in line:
                    if "Wavefunction not fully converged!" in line:
                        print("WARNING: SCF didn't fully converge in {}".format(self.path))
                    outdict['final_energy'] = float(line.split()[4])
                if "Sum of individual times" in line:
                    outdict['runtime'] = float(line.split()[5])
                if "****ORCA TERMINATED NORMALLY****" in line:
                    outdict["finished_normally"] = True
                if "N(Total)" in line:
                    outdict["n_electrons"] = int(np.floor(float(line.split()[-2])))
                if  "NO   OCC          E(Eh)            E(eV)" in line:
                    MoEnergyBlock = True
                    continue
                if MoEnergyBlock:
                    occ = float(line.split()[1])
                    energy = float(line.split()[-1])
                    if occ == 1:
                        outdict["homo_ev"] = energy
                    else:
                        outdict["lumo_ev"] = energy
                        MoEnergyBlock = False
                if "frequencies" in line.lower():
                    FreqCalc = True
                    continue
                if FreqCalc and "***imaginary mode***" in line:
                    outdict["has_imaginary_freq"] = True
                if "Final Gibbs free energy" in line:
                    outdict["gibbs_free_energy"] = float(line.split()[-2])
            # after scanning the file, if frequency calc and not found imaginary freq => no imaginary freq in calc
            if FreqCalc and outdict["has_imaginary_freq"] is None:
                outdict["has_imaginary_freq"] = False
        return outdict

    def read_specie(self):
        outdict = {
            "atom_symbols": None,
            "atom_coords": None,
            "bondmap": None
        }

        with open(self.path, "r", encoding="utf8") as f:
            MoleculeBlock = False
            for line in f.readlines():
                if "CARTESIAN COORDINATES (ANGSTROEM)" in line:
                    MoleculeBlock = True
                    outdict['atom_symbols'] = []
                    outdict['atom_coords'] = []
                    continue
                if "--------" in line:
                    continue
                if len(line) < 2:
                    MoleculeBlock = False
                if MoleculeBlock:
                    v = line.split()
                    outdict['atom_symbols'].append(v[0])
                    outdict['atom_coords'].append([float(x) for x in v[-3:]])
        # creating Molecule object
        atoms = [Atom(s, np.array(c)) for s, c in zip(outdict["atom_symbols"], outdict["atom_coords"])]
        return Molecule(atoms)

    def read_loewdin_reduced_orbital_populations(self, focus_orbitals=None, spin=None):
        """Method to read Loewdin reduced orbital populations per MO output from ORCA (got with NormalPrint option).
        ARGS:
            - focus_orbitals (List[str]): list of orbitals to focus on (for example O_px for px orbitals on oxygen atoms in the molecule). default None
            - spin (str): spin to make loewdin analysis for ("UP" or "DOWN") in case of unrestricted calculation. default None
        RETURNS:
            (pd.DataFrame) dataframe with all loewdin orbital populations for all desired orbitals (all orbitals if focus_orbitals=None)"""
        with open(self.path, "r", encoding="utf8") as f:
            LoewdinBlock = False
            title_line_no = 0
            res = pd.DataFrame()
            current = pd.DataFrame()
            TableBlock = False
            for counter, line in enumerate(f.readlines()):
                splitted = line.strip().split()
                if "LOEWDIN REDUCED ORBITAL POPULATIONS PER MO" in line:
                    LoewdinBlock = True
                    continue
                if not spin is None:
                    opposite_spin_text = "SPIN UP" if spin.lower() == 'down' else "SPIN DOWN"
                    spin_text = "SPIN " + spin.upper()
                    # stops parsing if read correct data (spin option is first)
                    if opposite_spin_text in line and not len(res) == 0:
                        break
                    # re-reads data if read false data (spin option is second)
                    elif spin_text in line and not len(res) == 0:
                        res = pd.DataFrame()
                        current = pd.DataFrame()
                if LoewdinBlock and len(splitted) == 6 and counter - title_line_no > 3:
                    title_line_no = counter
                    res = pd.concat([res, current])
                    current = pd.DataFrame(index=[int(s) for s in splitted])
                    continue
                if LoewdinBlock and counter - title_line_no == 1:
                    current["energy [Ha]"] = [float(s) for s in splitted]
                if LoewdinBlock and counter - title_line_no == 2:
                    current["occupation"] = [float(s) for s in splitted]
                if LoewdinBlock and counter - title_line_no == 3 :
                    TableBlock = True
                    continue
                if len(splitted) == 0:
                    TableBlock = False
                    continue
                if TableBlock:
                    if focus_orbitals is None:
                        current["_".join(splitted[:3])] = [float(s) for s in splitted[3:]]
                    elif "_".join(splitted[1:3]) in focus_orbitals:
                        current["_".join(splitted[:3])] = [float(s) for s in splitted[3:]]
                    continue
                if "****************" in line:
                    LoewdinBlock = False
            return res.fillna(0)

    def write_file(self, specie, kwdict):
        return super().write_file(specie, kwdict)