from bbpipe import PipelineStage
from .types import FitsFile, TextFile
import numpy as np
import pylab as pl
import pymaster as nmt
import healpy as hp
from fgbuster.cosmology import _get_Cl_cmb 
from fgbuster.mixingmatrix import MixingMatrix
import scipy.constants as constants
from astropy.cosmology import Planck15


def binning_definition(nside, lmin=2, lmax=200, nlb=[], custom_bins=False):
    if custom_bins:
        ells=np.arange(3*nside,dtype='int32') #Array of multipoles
        weights=(1.0/nlb)*np.ones_like(ells) #Array of weights
        bpws=-1+np.zeros_like(ells) #Array of bandpower indices
        i=0;
        while (nlb+1)*(i+1)+lmin<lmax :
            bpws[(nlb+1)*i+lmin:(nlb+1)*(i+1)+lmin]=i
            i+=1 
        ##### adding a trash bin 2<=ell<=lmin
        # bpws[lmin:(nlb+1)*i+lmin] += 1
        # bpws[2:lmin] = 0
        # weights[2:lmin]= 1.0/(lmin-2-1)
        b=nmt.NmtBin(nside,bpws=bpws, ells=ells, weights=weights)
    else:
        b=nmt.NmtBin(nside, nlb=int(1./self.config['fsky']))
    return b

def B(nu, T):
    x = constants.h * nu / constants.k / T
    return 2. * constants.h * (nu) ** 3 / constants.c ** 2 / np.expm1(x)

def dB(nu, T):
    x = constants.h * nu / constants.k / T
    return B(nu, T) / T * x * np.exp(x) / np.expm1(x)

def KCMB2RJ(nu):
    return  dB(nu, Planck15.Tcmb(0).value) / (2. * (nu / constants.c) ** 2 * constants.k)


class BBClEstimation(PipelineStage):
    """
    Stage that performs estimate the angular power spectra of:
        * each of the sky components, foregrounds and CMB, as well as the cross terms
        * of the corresponding covariance
    """

    name='BBClEstimation'
    inputs=[('binary_mask_cut',FitsFile),('post_compsep_maps',FitsFile), ('post_compsep_cov',FitsFile),
            ('A_maxL',TextFile),('noise_maps',FitsFile), ('post_compsep_noise',FitsFile)]
    outputs=[('Cl_clean', FitsFile),('Cl_noise', FitsFile),('Cl_cov_clean', FitsFile),('Cl_cov_freq', FitsFile)]

    def run(self):

        clean_map = hp.read_map(self.get_input('post_compsep_maps'),verbose=False, field=None, h=False)
        cov_map = hp.read_map(self.get_input('post_compsep_cov'),verbose=False, field=None, h=False)
        A_maxL = np.loadtxt(self.get_input('A_maxL'))
        noise_maps=hp.read_map(self.get_input('noise_maps'),verbose=False, field=None)
        post_compsep_noise=hp.read_map(self.get_input('post_compsep_noise'),verbose=False, field=None)

        nside_map = hp.get_nside(clean_map[0])
        print('nside_map = ', nside_map)
        
        w=nmt.NmtWorkspace()
        b = binning_definition(self.config['nside'], lmin=self.config['lmin'], lmax=self.config['lmax'],\
                                         nlb=self.config['nlb'], custom_bins=self.config['custom_bins'])

        print('building mask ... ')
        mask =  hp.read_map(self.get_input('binary_mask_cut'))
        mask_apo = nmt.mask_apodization(mask, self.config['aposize'], apotype=self.config['apotype'])

        print('building ell_eff ... ')
        ell_eff = b.get_effective_ells()

        #Read power spectrum and provide function to generate simulated skies
        cltt,clee,clbb,clte = hp.read_cl(self.config['Cls_fiducial'])[:,:4000]
        mp_t_sim,mp_q_sim,mp_u_sim=hp.synfast([cltt,clee,clbb,clte], nside=nside_map, new=True, verbose=False)

        def get_field(mp_q,mp_u,purify_e=False,purify_b=True) :
            #This creates a spin-2 field with both pure E and B.
            f2y=nmt.NmtField(mask_apo,[mp_q,mp_u],purify_e=purify_e,purify_b=purify_b)
            return f2y

        #We initialize two workspaces for the non-pure and pure fields:
        f2y0=get_field(mask*mp_q_sim,mask*mp_u_sim)
        w.compute_coupling_matrix(f2y0,f2y0,b)

        #This wraps up the two steps needed to compute the power spectrum
        #once the workspace has been initialized
        def compute_master(f_a,f_b,wsp) :
            cl_coupled=nmt.compute_coupled_cell(f_a,f_b)
            cl_decoupled=wsp.decouple_cell(cl_coupled)
            return cl_decoupled

        ### compute noise bias in the comp sep maps
        Cl_cov_clean_loc = []
        for f in range(len(self.config['frequencies'])):
            fn = get_field(mask*noise_maps[3*f+1,:]*KCMB2RJ(150.0), mask*noise_maps[3*f+2,:]*KCMB2RJ(150.0))
            # hp.mollview(noise_maps[3*f+1,:], title='Q', sub=121)
            # hp.mollview(noise_maps[3*f+2,:], title='U', sub=122)
            Cl_cov_clean_loc.append(1.0/compute_master(fn, fn, w)[3] )
            # pl.figure()
            # pl.loglog(1.0/compute_master(fn, fn, w)[3])
            # pl.show()
        AtNA = np.einsum('fi, fl, fj -> lij', A_maxL, np.array(Cl_cov_clean_loc), A_maxL)
        # print('shape of AtNA = ', AtNA.shape)
        # print('AtNA = ', AtNA)
        inv_AtNA = np.linalg.inv(AtNA)
        # print('shape of inv_AtNA = ', inv_AtNA.shape)
        # print('inv_AtNA = ', inv_AtNA)
        Cl_cov_clean = np.diagonal(inv_AtNA, axis1=-2,axis2=-1)
        # print('shape of Cl_cov_clean = ', Cl_cov_clean.shape)
        # print('Cl_cov_clean = ', Cl_cov_clean)       
        Cl_cov_clean = np.vstack((ell_eff,Cl_cov_clean.swapaxes(0,1)))
        # print('shape of Cl_cov_clean = ', Cl_cov_clean.shape)
        # print('Cl_cov_clean = ', Cl_cov_clean)          
        # exit()
        ### for comparison, compute the power spectrum of the noise after comp sep

        ### compute power spectra of the cleaned sky maps
        ncomp = int(len(clean_map)/2)
        Cl_clean = [ell_eff] 
        Cl_noise = [ell_eff] 
        components = []
        print('n_comp = ', ncomp)
        ind=0
        for comp_i in range(ncomp):
            # for comp_j in range(ncomp)[comp_i:]:
            comp_j = comp_i
            print('comp_i = ', comp_i)
            print('comp_j = ', comp_j)

            components.append(str((comp_i,comp_j))) 

            ## signal spectra
            if comp_i > 1: purify_b_=False
            else:purify_b_=True
            fyp_i=get_field(mask*clean_map[2*comp_i], mask*clean_map[2*comp_i+1], purify_b=purify_b_)
            fyp_j=get_field(mask*clean_map[2*comp_j], mask*clean_map[2*comp_j+1], purify_b=purify_b_)

            Cl_clean.append(compute_master(fyp_i, fyp_j, w)[3])

            ## noise spectra
            fyp_i_noise=get_field(mask*post_compsep_noise[2*comp_i], mask*post_compsep_noise[2*comp_i+1], purify_b=True)
            fyp_j_noise=get_field(mask*post_compsep_noise[2*comp_j], mask*post_compsep_noise[2*comp_j+1], purify_b=True)

            Cl_noise.append(compute_master(fyp_i_noise, fyp_j_noise, w)[3])

            ind += 1

        print('ind = ', ind)
        print('shape(Cl_clean) = ', len(Cl_clean))
        print('shape(array(Cl_clean)) = ', (np.array(Cl_clean)).shape)
        print('all components = ', components)
        print('saving to disk ... ')
        hp.fitsfunc.write_cl(self.get_output('Cl_clean'), np.array(Cl_clean), overwrite=True)
        hp.fitsfunc.write_cl(self.get_output('Cl_noise'), np.array(Cl_noise), overwrite=True)
        hp.fitsfunc.write_cl(self.get_output('Cl_cov_clean'), np.array(Cl_cov_clean), overwrite=True)
        hp.fitsfunc.write_cl(self.get_output('Cl_cov_freq'), np.array(Cl_cov_clean_loc), overwrite=True)

if __name__ == '__main__':
    results = PipelineStage.main()
    