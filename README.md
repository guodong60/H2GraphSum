# H2Graphsum

This is the implementation of the H2Graphsum approach.

# Runtime Environment

- 2 NVIDIA 4090 GPUs 
- Ubuntu 20.04.3 LTS
- CUDA 12.0 (with CuDNN of the corresponding version)
- Python 3.9
- PyTorch 1.11.0
- PyTorch Geometric 2.0.4 

# Dataset

The whole datasets of Python and Java can be downloaded from [[Google Drive]https://drive.google.com/drive/folders/1kl8VBLxbVJUvV3aEF-Nx659d7Rkz86_Z?usp=drive_link.


**Note that:** 

- We provide 100 samples for train/valid/test datasets in the directory `data/python/raw_data/`, `data/java/raw_data/`, and `data/python_GypSum/raw_data/`. 
- The python_GypSum dataset was originally built by the work [GypSum: Learning Hybrid Representations for Code Summarization](https://arxiv.org/pdf/2204.12916.pdf) for the model evaluation on the cleaned testing set, which is different from the python dataset in `data/python/raw_data/`.
- To run on the whole datasets,
  please download them from [Google Drive](https://drive.google.com/file/d/1eXCJEkCWuxi8xqMa_XAjg6OH4DNknT35/view?usp=share_link) for usage.

# Experiment on the Python(Java/Python_GypSum) Dataset

1. Step into the directory `src_code/python(java,python_GypSum)/code_sum_41`:

   ```angular2html
   cd src_code/python/code_sum_41
   ```

   or

   ```angular2html
   cd src_code/java/code_sum_41
   ```

   or

   ```angular2html
   cd src_code/python_GypSum/code_sum_41
   ```

2. Pre-process the train/valid/test data:

   ```angular2html
   python s1_preprocessor.py
   ```

    **Note that:**
    It will take hours for pre-processing the whole dataset.

3. Run the model for training, validation, and testing:

   ```angular2html
   python s2_model.py
   ```

After running, the console will display the performances on the whole testing of the python/java datasets and the performance on the cleaned testing set of the python_GypSum dataset. The predicted results of testing data, along with the ground truth and source code, will be saved in the path `data/python(java,python_GypSum)/result/codescriber_v1_6_8_512.json` for observation.

We have provided the results of the whole testing sets. The user can get the evaluation results on the whole python/java testing sets directly by running 

```angular2html
python s3_eval_whole_test_set.py"
```

The user can also get the evaluation results on the cleaned java/python_GypSum testing sets by directly run

```angular2html
python s3_eval_cleaned_test_set.py"
```

**Note that:** 

- All the parameters are set in `src_code/python(java,python_GypSum)/config.py`.
- If a model has been trained, you can set the parameter "train_mode" in `config.py` to "False". Then you can predict the testing data directly by using the model that has been saved in `data/python/model/`.
- We have provided in [Google Drive](https://drive.google.com/file/d/1eXCJEkCWuxi8xqMa_XAjg6OH4DNknT35/view?usp=share_link) all the files including the trained models as well as the log files of training processes (in `data/python(java,python_GypSum)/log/`). The user can download them for reference and model evaluation without running `s1_preprocessor.py` and model training. Still, don't forget to set the parameter "train_mode" in `config.py` to "False" for direct prediction and evaluation with these files.
