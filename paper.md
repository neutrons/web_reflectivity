---
title: 'Web Interface for reflectivity fitting'
tags:
  - neutron reflectivity analysis
  - data processing
  - user interface
authors:
 - name: Mathieu Doucet
   orcid: 0000-0002-5560-6478
   affiliation: 1
 - name: Ricardo Miguel Ferraz Leal
   orcid: 0000-0002-9931-8304
   affiliation: 1
 - name: T. C. Hobson
   affiliation: 1
affiliations:
 - name: Oak Ridge National Laboratory
   index: 1
date: August 11, 2017
bibliography: paper.bib
---

# Summary
The Liquids Reflectometer (LR) is one of the two reflectometers at the Oak Ridge National
Laboratory’s Spallation Neutron Source (SNS) [@Mason]. Specular reflectivity allows us to
probe the depth profile of thin planar films by measuring the reflected distribution of beams of
neutrons or X-ray photons scattered off their surface [@Sivia]. In the case of the LR, neutron reflectivity
measurements allow us to probe layer structures with length scales between a few Angstroms and a
few thousand Angstroms.

The number of experiments performed at the Liquids Reflectometer at the SNS demands a
streamlining of data processing so that users leave the laboratory with quality data sets and a clear
plan for how they are going to analysis them. An important part of this effort is to offer analysis tools
that empower users to work independently regardless of whether they have a background in scientific
computing or not. To address this need, we developed a user interface that simplifies the work of
modeling reflectivity data. By deploying it as a web application, we have also greatly reduced the
problem of installing software on various platforms, and we have made the transition from the
laboratory to the home institution seamless. The reflectivity fitting application lets users manage their
fit jobs, their models, and their data files. It provides a simple interface that lets users concentrate on
the science by removing the need to install software or write Python scripts.

The calculation of the reflectivity profile from a layered system is generally done by following the
reflected and transmitted particle waves at the layer boundaries [@Abeles][@Parratt].
REFL1D [@Kienzle] is a scripting Python package that also provides minimization and error analysis of reflectivity models.
The application developed here generates REFL1D scripts, submits them for execution, and manages the results.

# References