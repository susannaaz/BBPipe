import numpy as np

from fgbuster.component_model import CMB

class Bandpass(object):
    def __init__(self, nu, dnu, bnu, bp_number, config, phi_nu=None):
        self.number = bp_number
        self.nu = nu
        self.bnu_dnu = bnu * dnu
        self.nu_mean = np.sum(CMB('K_RJ').eval(self.nu) * self.bnu_dnu * nu * nu**2) / \
                       np.sum(CMB('K_RJ').eval(self.nu) * self.bnu_dnu * nu**2)
        field = 'bandpass_%d' % bp_number

        # Get frequency-dependent angle if necessary
        try:
            fname = config['systematics']['bandpasses'][field]['phase_nu']
        except KeyError:
            fname = None
            self.is_complex = False
        if fname:
            from scipy.interpolate import interp1d
            nu_phi, phi = np.loadtxt(fname,unpack=True)
            phif = interp1d(nu_phi, np.radians(phi),
                          bounds_error=False, fill_value=0)
            phi_arr = phif(self.nu)
            phase = np.cos(2*phi_arr) + 1j * np.sin(2*phi_arr)
            self.bnu_dnu = self.bnu_dnu * phase
            self.is_complex = True

        # Checking if we'll be sampling over bandpass systematics
        self.do_shift = False
        self.name_shift = None
        self.do_gain = False
        self.name_gain = None
        self.do_angle = False
        self.name_angle = None
        self.do_dphi1 = False
        self.name_dphi1 = None
        try:
            d = config['systematics']['bandpasses'][field]['parameters']
        except KeyError:
            d = {}
        for n, p in d.items():
            if p[0] == 'shift':
                self.do_shift = True
                self.name_shift = n
            if p[0] == 'gain':
                self.do_gain = True
                self.name_gain = n
            if p[0] == 'angle':
                self.do_angle = True
                self.name_angle = n
            if p[0] == 'dphi1':
                self.do_dphi1 = True
                self.is_complex = True
                self.name_dphi1 = n
        return

    def convolve_sed(self, sed, params):
        dnu = 0.
        dphi1_phase = 1.
        if self.do_shift:
            dnu = params[self.name_shift] * self.nu_mean
        
        if self.do_dphi1:
            dphi1 = params[self.name_dphi1]
            normed_dphi1 = dphi1 * np.pi / 180. * (self.nu - self.nu_mean) / self.nu_mean
            dphi1_phase = np.cos(2.*normed_dphi1) + 1j * np.sin(2.*normed_dphi1)

        nu_prime = self.nu + dnu
        cmb_norm = np.sum( CMB('K_RJ').eval(nu_prime) * self.bnu_dnu * nu_prime**2 )
        conv_sed = np.sum( sed(nu_prime) * self.bnu_dnu * dphi1_phase * nu_prime**2 ) / cmb_norm

        if self.do_gain:
            conv_sed *= params[self.name_gain]

        if self.is_complex:
            mod = abs(conv_sed)
            cs = conv_sed.real/mod
            sn = conv_sed.imag/mod
            return mod, np.array([[cs,sn],[-sn,cs]])
        else:
            return conv_sed, np.identity(2)

    def get_rotation_matrix(self, params):
        if self.do_angle:
            phi = params[self.name_angle] * np.pi / 180.
            c=np.cos(2.*phi)
            s=np.sin(2.*phi)
            return np.array([[c,s],[-s,c]])
        else:
            return np.identity(2)

def rotate_cells_mat(mat1, mat2, cls):
    cls=np.einsum('ijk,lk',cls,mat1)
    cls=np.einsum('jk,ikl',mat2,cls)
    return cls

def rotate_cells(bp1, bp2, cls, params):
    m1=bp1.get_rotation_matrix(params)
    m2=bp2.get_rotation_matrix(params)
    return rotate_cells_mat(m1,m2,cls)

def decorrelated_bpass(bpass1, bpass2, sed, params, decorr_delta):
    def convolved_freqs(bpass):
        dnu = 0.
        dphi1_phase = 1.
        if bpass.do_shift:
            dnu = params[bpass.name_shift] * bpass.nu_mean
        if bpass.do_dphi1:
            dphi1 = params[bpass.name_dphi1]
            normed_dphi1 = dphi1 * np.pi / 180. * (bpass.nu - bpass.nu_mean) / bpass.nu_mean
            dphi1_phase = np.cos(2.*normed_dphi1) + 1j * np.sin(2.*normed_dphi1)
        nu_prime = bpass.nu + dnu
        cmb_norm = np.sum( CMB('K_RJ').eval(nu_prime) * bpass.bnu_dnu * nu_prime**2 )
        bphi = bpass.bnu_dnu * dphi_phase_1 * nu_prime**2 * sed(nu_prime)
        return nu_prime, cmb_norm, bphi

    nu_prime1, cmb_norm1, bphi1 = convolved_freqs(bpass1)
    nu_prime2, cmb_norm2, bphi2 = convolved_freqs(bpass2)
    nu1nu2 = np.outer(nu_prime1, 1./nu_prime2)
    decorr_exp = decorr_delta**(np.log(nu1nu2)**2)
    decorr_sed = np.einsum('i, ij, j', bphi1, decorr_exp, bphi2) / cmb_norm1 / cmb_norm2

    if bpass1.do_gain:
        decorr_sed *= params[bpass1.name_gain]
    if bpass2.do_gain:
        decorr_sed *= params[bpass2.name_gain]

    # help
    if self.is_complex:
        mod = abs(decorr_sed)
        cs = decorr_sed.real/mod
        sn = decorr_sed.imag/mod
        return mod, np.array([[cs,sn],[-sn,cs]])
    else:
        return decorr_sed, np.identity(2)
    



