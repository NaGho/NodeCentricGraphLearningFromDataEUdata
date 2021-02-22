# Node Centric Graph Learning From Brain Data 
In this repository, we have implemented the "Node-Centric Graph Learning" algorithm from brain data. Please refer to our paper [1] for the detailes. The code is built up on the graphSAGE representation learning code [2], and is modified in many ways. We our proposed graph learning algorithm for brain state identification and more specificly for seizure detection. 

The ECoG recordings that are used as data on which classification is applied, are sampled from the extensive EPILEPSAE data set [3] which is not publicly accessible to public. Hence, little changes are needed to be applied to the code for its usage on other datasets.

The main part of the code is in the "main.py" file. The "supervised_tasks.py" contains majority of high-level and important functions of this project.

Please cite our paper 
    [1] Ghoroghchian, N., Groppe, D. M., Genov, R., Valiante, T. A., & Draper, S. C. (2020). Node-Centric Graph Learning From Data for Brain State Identification. 
    IEEE Transactions on Signal and Information Processing over Networks, 6, 120-132.
when using the code in this directory.

Other references:
[2] W. Hamilton, Z. Ying, and J. Leskovec, “Inductive representation learning on large graphs,” in Proc. Adv. Neural Inf. Process. Syst., 2017, pp. 1025–1035.
[3] M. Ihle et al., “Epilepsiae–A european epilepsy database,” Comput.Methods Programs Biomedicine, vol. 106, no. 3, pp. 127–138, 2012.

