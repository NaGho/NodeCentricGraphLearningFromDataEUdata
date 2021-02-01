# Node Centric Graph Learning From Brain Data 
In this repository, we have implemented the proposed "Node-Centric Graph Learning" algorithm from data in our paper [1]. The code is built up on the graphSAGE representation learning code [2], and is modified in many ways. We our proposed graph learning algorithm for brain state identification and more specificly for seizure detection. 

The ECoG recordings that are used as data on which classification is applied, are sampled from the extensive EPILEPSAE data set [3] which is not publicly accessible to public. Hence, little changes are needed to be applied to the code for its usage on other datasets.

Please start reading the code from "main.py" file. The "supervised_tasks.py" contains majority of high-level and important functions of this project.
