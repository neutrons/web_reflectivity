#pylint: disable=bare-except, invalid-name, too-many-arguments, unused-argument, line-too-long
"""
    Forms for web reflectivity
"""
import periodictable as pt
import periodictable.nsf as nsf
from django import forms
from django.utils.safestring import mark_safe

class ChargeRateForm(forms.Form):
    """
        Input form for the capacity calculator
    """
    material_formula = forms.CharField(label='Material', max_length=100, initial='Si')
    electrode_radius = forms.FloatField(label='Electrode radius [cm]', initial=2)
    electrode_thickness = forms.FloatField(label='Electrode thickness [nm]', initial=75)
    ion_packing = forms.FloatField(label="Stoichiometry", initial=3.75)
    valence_change = forms.IntegerField(label="Oxidation state change", initial=1)
    electrode_density = forms.FloatField(label=mark_safe("Material density [g/cm<sup>3</sup>]"), required=False)

    def capacity(self):
        """
            Calculate capacity [micro Ah]

            The charge packing refers, for instance, to the maximum x in Li_x:Si.

            To test: Li_15 Si_4 -> 3579 mAh

            :param electrode: electrode composition [string]
            :param radius: electrode radius [cm]
            :param thickness: electrode thickness [nm]
            :param packing: charge packing
            :param valence_change: change in oxidation state of the carrier
        """
        N_a = 6.022*10**23
        # Charge unit in Coulombs
        q = 1.602*10**(-19)

        electrode_material = pt.formula(self.cleaned_data['material_formula'])
        density = self.cleaned_data['electrode_density']
        if density is None:
            density = electrode_material.density # g/cm^3
        if density is None:
            return None

        atomic_weight = electrode_material.mass # g/mol

        volume = 3.1416 * self.cleaned_data['electrode_radius']**2 * self.cleaned_data['electrode_thickness']/10**7

        # Amp*hour = Coulombs/sec * 3600 sec = 3600 Coulombs
        capacity_per_gram = self.cleaned_data['ion_packing']*q*self.cleaned_data['valence_change']/3600/atomic_weight*N_a*1000
        capacity = volume * density * capacity_per_gram

        # Scattering length density
        # sld, imaginary sld, incoherent
        sld, im_sld, incoh = nsf.neutron_sld(compound=self.cleaned_data['material_formula'], wavelength=6.0, density=density)

        # Return value in muAh
        return dict(capacity='%6.3g' % capacity, sld='%6.3f' % sld,
                    im_sld='%6.6f' % im_sld, incoherent='%6.3f' % incoh,
                    density=density,
                    c_over_3='%6.3g' % (capacity/3.0),
                    c_over_5='%6.3g' % (capacity/5.0))
