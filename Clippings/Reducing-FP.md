---
title: "AI-Enhanced Static Analysis: Reducing False Alarms Using Large Language Models"
source: "https://ieeexplore.ieee.org/document/11058686"
author:
published:
created: 2026-08-20
description: "In modern software systems, early and accurate vulnerability detection is crucial. Traditional Static Analysis Tools (SATs) highlight potential security issues,"
tags:
  - "clippings"
---
## Abstract:

In modern software systems, early and accurate vulnerability detection is crucial. Traditional Static Analysis Tools (SATs) highlight potential security issues, providing...

---

In modern software engineering, where the developed software products are often large, complex, and interconnected, the need to develop secure software by design has increased. In accordance with the International Standard on Software Quality ISO/IEC 25010 \[1\], software security is now considered a critical aspect of the Software Development Life-Cycle (SDLC). The main focus of software security is on addressing vulnerabilities that reside in source code. Commonly, software vulnerabilities are caused by errors during the code development phase, but their exploitation by external threats can lead to serious consequences both financially and in terms of data privacy, confidentiality, etc. Various techniques for software vulnerability mitigation have been proposed \[2\]. However, the continuous increase in security breaches and reported vulnerabilities in the National Vulnerability Database (NVD) \[3\] indicates that existing solutions are not sufficient.

Traditionally, the detection of vulnerabilities in the source code is performed through static analysis using tools such as Fortify, Coverity, SonarQube, CppCheck. \[4\], \[5\]. These Static Analysis Tools (SATs) detect issues via a white-box testing approach and without executing the source code, by automatically checking the source code against a list of predefined by experts rules and patterns, managing to return information on potential vulnerabilities, including their location, type, and severity \[5\].

However, despite its strengths, static analysis remains underutilized in practice \[6\], \[7\] due to the important challenges that it faces \[8\], with the most critical being the overwhelming number of False Positives (FPs) that it produces, which hinders its adoption in practice \[9\], \[10\]. In particular, the extensive alert lists produced by SATs require manual inspection by developers and code reviewers to identify the actionable alerts (i.e., alerts that correspond to actual bugs that require immediate fix). This time-consuming and labor-intensive procedure, known as triaging \[6\], hinders the adoption of SATs in practice. To this end, recent research attempts have focused on addressing the issue of FPs by developing methods to post-process the produced alerts to identify which ones are actionable \[11\]–\[13\].

Apart from traditional static analysis tools, another promising mechanism that has emerged relatively recently in the field of vulnerability detection is Vulnerability Prediction (VP), which aims at predicting vulnerable software components (e.g., packages, files, functions, snippets). Specifically, VP is a Machine Learning (ML)-driven mechanism, which uses software attributes, such as software metrics \[14\], \[15\] or textual features \[15\]–\[18\] to classify software components as vulnerable or clean. Contrary to traditional static analysis that is based on the identification of violations of specific rules and best practices, VP is able to detect more complex vulnerability patterns, due to the utilization of advanced AI algorithms. More specifically, with the emergence of the Transformer architecture \[19\] and the Large Language Models (LLMs), enhanced VP solutions have been proposed \[20\], \[21\].

However, the vast majority of the proposed Vulnerability Prediction Models (VPMs) perform predictions at class- or function-level of granularity \[2\], \[20\], and are not able to provide specific information about the actual location and type of the detected vulnerability. Although there have been some studies recently that utilize explainable AI (XAI) techniques to trace the vulnerability patterns detected by the VPMs at the line level \[22\]–\[24\], they exhibit important drawbacks, the most significant being the inclusion of spurious features (i.e., code constructs that are irrelevant to the existence of vulnerabilities) thereby misleading the detection process \[25\], \[26\].

Based on the above analysis, it is clear that both SATs and VPMs are useful for detecting vulnerabilities that reside in the source code of software applications, with each one providing its own benefits and facing its own challenges. Hence, instead of relying solely on one of them for vulnerability detection (e.g., traditionally SATs and recently VPMs), an interesting direction would be to examine whether the utilization of AI-based vulnerability prediction models could help improve the practicality of traditional static analysis, by reducing the volume of false alarms. This can be expressed more formally in the following research question:

- **RQ**: Can we leverage AI-based vulnerability prediction models for improving the practicality of static analysis?

To this end, in the current study we investigate whether the utilization of AI-based VPMs could reduce the number of false positives produced by static analysis, thereby improving its practicality, and analyzing potential consequences for overall detection accuracy. More specifically, we use a popular static code analyzer as the primary SAT to identify potential security issues and an LLM-based VPM to predict vulnerable functions. Only those alerts associated with functions marked as vulnerable by the LLM-based VPMs are retained and considered actionable, with the rest being considered non-actionable. An analysis of the impact of this filtering process on the practicality and predictive performance of the selected static analysis tool is performed, based on two well-known and widely-used vulnerability datasets containing real-world vulnerabilities.

The structure of this study is as follows. Section II provides an overview of the related literature. Subsequently, Section III describes the proposed methodology, and Section IV presents the evaluation results of our analysis. Finally, in Section VI the study is concluded, and directions for future work are proposed.

This section presents the related work on vulnerability detection techniques used to identify vulnerabilities in source code. We discuss the existing static code analysis techniques and the background on the more recent concept of vulnerability prediction.

### A. Static Code Analysis

Several research initiatives that aim to enhance software quality and security based on static analysis have been proposed over the years \[5\], \[27\]. Static analysis tools play a vital role in evaluating source code and detecting potential vulnerabilities without requiring code execution. Their ability to identify issues early in the SDLC assists engineers in coding defensively. This is particularly beneficial in agile development, in cases where teams prioritize continuous delivery \[28\].

Well-known SATs in both industry and research areFortify, Checkmarx, Veracode, and Coverity among others \[4\], \[29\]. Though used extensively in both academia and business, SATs have well-documented limits that compromise their efficacy. Their tendency to produce false positives, which are warnings for issues that do not really exist or do not pose an actual security threat, is an important disadvantage that may over-whelm developers, reduce trust, and increase inspection effort \[6\], \[30\]. Furthermore, in attempts to minimize false positives, many tools adopt unsound analysis techniques that trade off precision for performance, often increasing false negatives (i.e., missing real vulnerabilities) \[30\]. Researchers emphasize that such tools often fail to provide efficient triage and prioritization of alerts, reducing their impact in real-world scenarios \[31\].

To address this challenge, researchers have explored various techniques to identify actionable alerts, i.e., alerts that correspond to actual bugs (including vulnerabilities) that require an immediate fix \[11\]. Various Actionable Alert Identification Techniques (AAITs) have been examined over the years, being based either on filtering out non-actionable alerts \[12\], or prioritizing the produced alerts based on their likelihood to be actionable \[13\]. Among the two types, the former is more appealing, as it leads to a significant reduction in the number of alerts reported by the SAT to the developers, and, in turn, in the time and effort required for checking and fixing the alerts.

However, the main challenge that existing AAITs face is their negative impact on the SAT's accuracy. More specifically, in their attempt to eliminate false positives, they inevitably introduce false negatives (i.e., they omit alerts that correspond to actual issues). Despite the advances in the field and the sophisticated techniques that have been employed, no AAITs exist that are able to eliminate false alarms without omitting actual issues. LLMs could potentially be a promising solution to alleviate this issue.

### B. Vulnerability Prediction

As highlighted in a recent systematic mapping study \[2\], significant progress has been made in the field of vulnerability prediction with the advancement of Machine Learning (ML) and Deep Learning (DL) techniques. Both software metrics (e.g., complexity, cohesion) \[32\], \[33\] and text mining techniques \[16\], \[17\], \[34\] have been thoroughly examined in the VP field, with the latter producing the best results \[14\], \[15\]. Moreover, text-rich graphs have been employed for better code representation, using Abstract Syntax Trees, Program Dependence Graphs, and Code Property Graphs \[35\], providing a promising direction in VP \[36\], \[37\].

Following the advances in the field of Natural Language Processing (NLP) with the emergence of the Transformer architecture \[19\], Large Language Models (LLMs) have emerged as a promising approach for VP. Their ability to understand natural and programming languages, code semantics, and contextual patterns enables more accurate prediction of vulnerabilities \[20\]. A comparison of word2vec, fastText, and pre-trained Bidi-rectional Encoder Representations from Transformers (BERT) \[38\] embeddings was conducted by Bagheri et al. \[39\], while Kim et al. \[40\] proposed VuIDeBERT, a BERT model fine-tuned for VP. In addition, a comparative analysis of various DL-based VPMs, including several LLMs, was performed by Steenhoek et al. \[21\], demonstrating the promising capacity of LLMs in VP. Kalouptsoglou et al. \[41\] also showed, among others, that LLMs surpass previous VPMs, including both text mining-based and graph-based approaches.

However, most VPMs make predictions at file- or function-level of granularity \[2\]. Recent attempts to highlight specific lines that are vulnerable leverage XAI techniques, such as Self-Attention \[42\], in order to identify the tokens and therefore the lines of code that contribute the most to a function-level decision of the VPM \[22\], \[24\]. Nevertheless, explanatory studies have discussed the limitations of this approach, since VPMs often make correct predictions by learning spurious data associations \[25\], \[26\]. Furthermore, creating such line-level models requires large databases with fine-grained labels, making the extension of such models across different programming languages a particularly difficult process.

Therefore, contrary to SATs which are able to pinpoint the exact lines of code where the vulnerability resides, AI-based VPMs, despite their observed higher accuracy in detecting vulnerability patterns (especially complex ones) than SATs, currently fail to provide information on the exact location and type of the detected vulnerability, which is highly useful and necessary for their correction by the development team. This greatly hinders their adoption in practice, as developers and engineers need to know the exact location and type of the detected vulnerability in order to be able to fix it, rendering the traditional static analysis still a more reliable approach.

### C. Beyond State-of-the-Art

The above analysis illustrates the need for combinatorial strategies to enhance existing SAST approaches. Although initial efforts have been made to reduce the number of static analysis alerts to focus on those that are actionable, it is clear that there is a need for integrated approaches that can combine intelligent alert filtering with the fine-grained information provided by static analysis. LLMs can be used to prioritize alerts that are more likely to be actionable, thereby greatly reducing the number of false alarms and, therefore, improve the practicality of static analysis outputs \[43\]. To this end, this paper uses static code analysis as its core method for detecting potential vulnerabilities and employs LLMs to prioritize the detected issues. In particular, by removing alerts from functions not considered vulnerable by the LLM-based VPMs we can isolate alerts that are more likely to correspond to real vulnerabilities. Thus, this method provides an important reduction in the effort required by developers and code reviewers to find vulnerabilities among the large lists of static analysis alerts.

This section presents the SAST methodology that is examined in this study. Initially, the vulnerability-related dataset that is used to conduct our analysis is described. We then describe the approach and evaluation procedure that we follow. Figure 1 provides an overview of the approach. Specifically, the source code of the functions of the vulnerability-related dataset is analyzed using both static analysis and VP, and the results are merged in order to retain those alerts found in the predicted-as-vulnerable functions. Those alerts, which include fine-grained information (i.e., lines and categories of vulnerabilities), are provided to a security expert or developer for review.

### A. Dataset

Regarding the datasets we used in this work, we chose two well-accepted vulnerability datasets that contain real-world vulnerabilities, namely the Big-Vul \[44\] and the ReVeal \[37\] datasets. They comprise C/C++ source code samples (i.e., functions) collected from publicly available GitHub repositories by linking commits to known vulnerabilities in the CVE Database. In order to conduct our experiments, parts of these datasets were used for training and validating the LLM-based VPM, whereas the test sets of the datasets were used as benchmarks to assess the benefits achieved by the examined approach (i.e., augmenting static analysis with information retrieved from VPMs), as opposed to utilizing solely traditional static analysis without any kind of alert filtering.

### B. Methodology

This section presents the methodology adopted in this study. We combined static code analysis with AI-based Vulnerability Prediction to enhance the identification of actionable static analysis alerts and, therefore, the detection of vulnerabilities. The entire process is illustrated in Figure 1 and comprises several key steps, including data preparation, static analysis, vulnerability prediction, merging the results, and comparative evaluation between the proposed methodology and the standalone static analysis solution.

First, we built a tool that employs the open-source CppCheck SAT to identify security-specific static analysis alerts in the functions of the datasets. In particular, we utilized the CppCheck plugin of the SonarQube platform in order to leverage the SonarQube API \[45\] for accessing the results of the analysis. The toolchain was implemented and configured in one of our prior studies \[46\].

In parallel, the same functions were fed to our VPM. First, they were tokenized and then given as input to the VPM to classify them as vulnerable or non-vulnerable. For the purposes of the current analysis, we employed a model developed in our previous work \[41\] by fine-tuning the CodeBERT LLM \[47\].

After both static analysis and VP were completed, their findings were combined. Specifically, we filtered out the functions that were not among those predicted as vulnerable by the VPM. Hence, we kept only those alerts reported by CppCheck that are included in predicted-as-vulnerable functions. This post-processed list of static analysis alerts was then given to the security reviewer to inspect and repair them.

Concisely, in the proposed method, VP predicts which functions are vulnerable, while the SAT identifies the lines and the categories of the security issues inside those functions. In this way, the proposed methodology reduces the inspection effort required to manually identify the actual vulnerabilities among all the identified issues, as a non-trivial number of alerts (i.e., those that belong to benign functions) are filtered out and not shown to the reviewer/developer immediately. Due to the inevitable Type I and Type II errors of the utilized models and techniques, an evaluation of both the detection efficacy and practicality of the proposed approach is conducted and presented in the next section (Section IV), in order to assess the benefits and shortcomings of the approach with respect to accuracy, precision, and practicality.

**Fig. 1.**

High-level overview of the methodology that combines static analysis with vulnerability prediction.

### C. Evaluation Schema

To evaluate the proposed methodology, an evaluation scheme that compares traditional static analysis with our AI-enhanced SAST approach was designed. The focus of the evaluation is on the capacity of the proposed method to reduce false positives generated by the selected static analysis tool and, in turn, the effort required for reviewing the static analysis findings without generating (at least too many) false negatives. This is important because it is known in the literature that AAITs, especially the classification-based techniques, inevitably introduce false negatives due to the filtering process that they employ (i.e., filtering out alerts that are considered non-actionable) \[11\]–\[13\]. Therefore, a quantification of this impact is important in order to evaluate whether the proposed AAIT is viable or un-realistic, i.e., whether the benefit in inspection effort reduction that is obtained by the model outweighs the omission of a small number of actionable alerts or the observed omissions are so many that any benefit in effort reduction is deemed worthless.

We computed the Precision, Recall, F <sub>1</sub> -score, and False Positive Rate (FPR) metrics. Given our focus on reducing FPs while identifying as many vulnerabilities as possible, the F <sub>1</sub> -score is utilized as the primary evaluation metric since it balances Precision and Recall through their harmonic mean. F <sub>1</sub> -score is defined as:

$$
\begin{equation*}
\mathrm{F}_1 \text{-score }=2 \cdot \frac{\text{ Precision } \cdot \text{ Recall }}{\text{ Precision }+ \text{ Recall }}
\tag{1}
\end{equation*}
$$
 View Source

Moreover, we consider the Inspection Ratio $\mathcal{(I)}$, which indicates the proportion of functions that need to be reviewed in order to identify all the actual vulnerabilities in the dataset. Lower values of $\mathcal{I}$ indicate reduced manual inspection over-head, making it especially relevant for real-world triage and auditing settings. This metric, which has been frequently used in the related literature \[14\], \[48\], captures the practical effort of manual inspection required and is defined as:

$$
\begin{equation*}
\mathcal{I}=\frac{TP+FP}{TP+FP+TN+FN}
\tag{2}
\end{equation*}
$$
 View Source

This equation is used to as a measure of practicality.

In this section, we evaluate whether the adoption of vulnerability prediction can improve the practicality of static analysis, examining the impact on the detection accuracy.

More specifically, the purpose of this evaluation is to investigate whether the use of LLMs can reduce the FPs of static analysis. To achieve this we examine the detection accuracy and inspection ratio of static analysis with and without the adoption of VPMs. As already mentioned, the analysis was based on two well-accepted vulnerability datasets, the Big-Vul and the ReVeal.

In the Big-Vul codebase, static analysis achieved a Precision of 5.88% and a Recall of 46.90%, resulting in a low F <sub>1</sub> -score of 10.46. The approach required the inspection of more than 50% of the dataset (Inspection Ratio = 50.49%) and produced a large number of false positives (FPR = 47.07%).

The AI-enhanced SAST methodology greatly improved Precision to 96.20%, essentially eliminating the majority of the false positives produced by the conventional static analysis. On the other hand, Recall dropped to 40.66%, while the overall F <sub>1</sub> -score increased to 57.16%. In addition, this methodology achieved a FPR of only 0.10%, demonstrating how effectively it filters out non-actionable alerts. Moreover, the Inspection Ratio also decreased to 2.44%, showing that this approach is more practical in real-world settings, managing to reduce the inspection effort required to find the actionable alerts.

As we can see, the results confirm the trade-off between Precision and Recall when combining the static analysis with the LLM. High false positive rates are often produced by the traditional SATs. When the VP is combined with static analysis, the Precision of the alerts improves greatly (Precision increased by approximately 90%) at the cost of reduced Recall (Recall decreased by approximately 6%). However, the reduction in Recall is much smaller compared to the improvement in Precision and Inspection Ratio, which may be considered preferable.

**Table I** Comparison of vulnerability detection methods on big-vul and reveal datasets

With respect to the ReVeal dataset, traditional static analysis achieved a Precision of 8.71%, Recall of 6.88%, and F <sub>1</sub> -score of 7.69. The FPR was 7.89%, and the Inspection Ratio was 15.41%. On the contrary, the combined approach was able to lower the FPR to 0.71%, confirming our method's filtering capacity. Although Recall slightly dropped to 5.93%, resulting in an F <sub>1</sub> -score of 10.56, the Inspection Ratio was by far lower (i.e., equal to 1.34%). The similar trend seen in the Big-Vul benchmark is confirmed by the result that the combinatorial method, although it does lead to a slight drop in Recall, improves Precision and reduces the inspection effort.

Overall, the study shows that even while traditional static analysis has slightly higher Recall, it has much lower Precision and a significant number of false positives. With low FPR and Inspection Ratios in both codebases, the proposed SAST approach greatly increases Precision while lowering noise. By lowering the Inspection Ratio to less than 3% in both cases, the approach demonstrates a high practical value. Concisely, we can argue that it is feasible to create a hybrid approach for accurate and practical vulnerability detection through the combination of static analysis with VP; however, this comes at the cost of a decrease in Recall, a known inherent issue of all AAITs in the literature, but this decrease is observed to be relatively small in our examined case. In addition, this drop in Recall may be considered acceptable in some domains.

This section provides a remark on threats to the validity of our study. Concerning construct validity, potential threats arise from the chosen evaluation metrics. We employ widely adopted metrics such as Precision, Recall, F <sub>1</sub> -score, and FPR, as well as an effort-aware metric (i.e., Inspection Ratio), mitigating this risk through alignment with established literature \[2\], \[14\].

Regarding internal validity, a key threat relates to potential errors or biases in the implementation of our approach. We carefully implemented a toolchain integrating CppCheck through SonarQube and a fine-tuned LLM-based VPM, but implementation errors might still exist. To mitigate this risk, we thoroughly reviewed our code and have also made the developed code publicly available to facilitate future replication and validation of our findings \[49\].

Finally, external validity threats concern the generalization of the findings, since we only used C/C++ data and the static analyzer CppCheck. However, the datasets used, which are Big-Vul \[44\] and ReVeal \[37\], are both widely referenced in vulnerability research \[2\], \[22\], \[23\], \[41\]. In addition, future research aims to explore additional languages, datasets, and analyzers to strengthen generalization.

In this study, we examined whether the practicality of static analysis could be improved through the adoption of AI-based vulnerability prediction. More specifically, we used the findings of an LLM-based VPM to filter out static analysis alerts that are not actionable (i.e., that do not correspond to actual vulnerabilities). The evaluation results were promising, demonstrating a significant decrease in the volume of the reported false alarms, with a relatively small omission of actionable alerts. This suggests that using LLM-based VPMs may be a viable solution for improving the practicality of static analysis, especially in contexts where a slight decrease in detection accuracy can be considered accentable.

Several directions for future work can be identified. After showing in this study that the use of LLMs as function-level vulnerability predictors can reduce the false alarms of traditional static analysis, next steps include investigating whether this approach surpasses existing AAITs by conducting a large-scale comparative study. Specific focus will be given on the drop in the Recall, in order to identify which technique achieves a better trade-off between Recall and Precision. We also aim at exploring whether the filtered-out alerts are of high or low severity. In addition, we are planning to analyze the impact of the studied approach by conducting a user study in order to receive feedback from developers and validate the practical us-ability of the filtered alerts, considering also the computational cost. We are also interested in repeating the current study using different SATs and for different programming languages.

### ACKNOWLEDGMENT

Work reported in this paper has received funding from the European Union's Horizon Europe Research and Innovation Program through the DOSS project, Grant Number 101120270.