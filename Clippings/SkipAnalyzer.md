---
title: "SkipAnalyzer: A Tool for Static Code Analysis with Large Language Models"
source: "https://arxiv.org/html/2310.18532v2"
author:
published:
created: 2026-08-20
description:
tags:
  - "clippings"
---
Mohammad Mahdi Mohajer <sup>1</sup>, Reem Aleithan <sup>2</sup>, Nima Shiri Harzevili <sup>3</sup>, Moshi Wei <sup>4</sup>,  
Alvine Boaye Belle <sup>5</sup>, Hung Viet Pham <sup>6</sup>, Song Wang <sup>7</sup> Affiliation: Lassonde School of Engineering, York University  
Toronto, Ontario, Canada  
{ <sup>1</sup> mmm98,<sup>2</sup> reem1100,<sup>3</sup> nshiri, <sup>4</sup> moshiwei,<sup>6</sup> hvpham,<sup>7</sup> wangsong}@yorku.ca; <sup>5</sup> alvine.belle@lassonde.yorku.ca

###### Abstract

We introduce SkipAnalyzer, a large language model (LLM)-powered tool for static code analysis. It can detect bugs, filter false positive warnings, and patch the detected bugs without human intervention. SkipAnalyzer consists of three components, 1) an LLM-based static bug detector that scans source code and reports specific types of bugs, 2) an LLM-based false-positive filter that can identify false-positive bugs in the results of static bug detectors (e.g., the result of step 1) to improve detection accuracy, and 3) an LLM-based patch generator that can generate patches for the detected bugs above. As a proof-of-concept, SkipAnalyzer is built on ChatGPT, which has exhibited outstanding performance in various software engineering tasks.

To evaluate SkipAnalyzer, we focus on two types of typical and critical bugs that are targeted by static bug detection, i.e., Null Dereference and Resource Leak as our subjects. We employ Infer to aid the gathering of these two bug types from 10 open-source projects. Consequently, our experiment dataset contains 222 instances of Null Dereference bugs and 46 instances of Resource Leak bugs. Our study demonstrates that SkipAnalyzer achieves remarkable performance in the mentioned static analysis tasks, including bug detection, false-positive warning removal, and bug repair. In static bug detection, SkipAnalyzer achieves accuracy values of up to 68.37% for detecting Null Dereference bugs and 76.95% for detecting Resource Leak bugs, improving the precision of the current leading bug detector, Infer by 12.86% and 43.13% respectively. For removing false-positive warnings, SkipAnalyzer can reach a precision of up to 93.88% for Null Dereference bugs and 63.33% for Resource Leak bugs. Additionally, SkipAnalyzer surpasses state-of-the-art false-positive warning removal tools. Furthermore, in bug repair, SkipAnalyzer can generate syntactically correct patches to fix its detected bugs with a success rate of up to 97.30%.

## I Introduction

Numerous static code analysis techniques have been utilized in the literature for the automatic detection of real-world software bugs [^1] [^2] [^3] [^4] [^5]. These tools typically rely on predefined heuristic rules to scan and analyze the codebases or binaries of software projects [^4] [^5] [^3]. During this analysis, any violations of these rules are categorized as a bug, leading the tools to flag the corresponding code artifact, such as a line or a group of lines, as buggy. However, employing static bug detectors presents specific challenges. One primary issue is that most static bug detectors generate numerous false-positive warnings [^6] [^7]. Consequently, additional manual review is essential to validate the reported potential bugs, resulting in a time-consuming and labor-intensive process [^8]. Additionally, these detected bugs still require manual fixes, demanding developers’ expertise and knowledge, which can be a resource-intensive task [^9] [^10].

Recently, Large Language Models (LLMs) such as ChatGPT have demonstrated significant potential in various reasoning and decision-making roles, serving as intelligent agents [^11] [^12], especially in SE tasks such as code generation, understanding, and debugging. However, to date, there has yet to be research exploring the capabilities of LLM-based tools for various static code analysis tasks. To address this gap, in this paper, we take a step toward developing a tool for code analysis based on LLMs named SkipAnalyzer. It contains three components: 1) an LLM-based static bug detector that is capable of scanning source code and reporting specific types of bugs, 2) an LLM-based false-positive filter for identifying false-positive bugs (e.g., those from step 1) to improve the detection accuracy, and 3) an LLM-based patch generator that can generate patches for the detected bugs. As a proof-of-concept, SkipAnalyzer is built on ChatGPT, which has consistently demonstrated outstanding performance in various software engineering tasks [^13].

To evaluate SkipAnalyzer, we select two typical and widely-studied bugs commonly targeted by static bug detection: Null Dereference and Resource Leak as our subjects. Following existing works [^14] [^15], we utilize Infer to facilitate the collection of these two types of bugs from 10 open-source projects. As a result, our experiment dataset includes 222 Null Dereference bugs and 46 Resource Leak bugs. When employing ChatGPT, we leverage two different model versions: 1) ChatGPT-3.5 Turbo and 2) ChatGPT-4. In this study, we adhere to the best practices of prompt engineering [^16] [^17] and create precise and context-aware prompts to effectively harness the language models’ capabilities. We explore various prompting strategies, including zero-shot, one-shot, and few-shot prompting, to evaluate the performance of different ChatGPT models across various scenarios. By strategically adapting our prompts and methodologies, we aim to identify the most efficient and accurate ways of leveraging LLMs in static analysis.

Our experiments reveal that SkipAnalyzer achieves remarkable performance with significant improvements when compared to previous baseline methods for each respective task: 1) Its LLM-based static bug detector achieves a precision rate that is 12.86% higher for Null Dereference bugs and 43.13% higher for Resource Leak bugs compared to Infer. 2) Its LLM-based false-positive filter can enhance Infer’s precision rate by 28.68% for Null Dereference bugs and 9.53% for Resource Leak bugs, surpassing the performance of existing baselines. Additionally, it can enhance the precision of SkipAnalyzer’s first component by 16.31% for Null Dereference bugs. 3) Its LLM-based patch generator can generate patches for the buggy codes and repair them with correctness rates of 97.30% and 91.77% for Null Dereference and Resource Leak bugs, respectively. Furthermore, on average, 98.77% of the generated code for both Null Dereference and Resource Leak bugs are syntactically correct.

As a summary, this paper contributes to the field in the following ways:

- We propose SkipAnalyzer, a large language model (LLM) powered tool for static code analysis that can detect bugs, filter false positive warnings, and patch the detected bugs without human intervention.
- We show that SkipAnalyzer can be an effective static bug detector, improving the base results of the current state-of-the-art tool, Infer.
- We demonstrate that SkipAnalyzer can effectively eliminate false-positive warnings from the output of static bug detectors such as Infer and its first component, thereby enhancing their precision and surpassing the performance of existing baseline methods in false-positive warning removal.
- We illustrate that SkipAnalyzer exhibits the capability to repair bugs identified by static bug detectors through the generation of accurate patches, which we compare against a baseline approach from prior research.
- We release the dataset and the source code for our experiments for future usages <sup>1</sup>.

The structure of the remainder of this paper is as follows: Section II presents the background of the study. Section III presents the data collection of the study. Section IV describes the proposed approach. Section V presents the experiment settings. Section VI presents the results of our work. Section VII presents the discussion. Section IX presents the related work. Section VIII presents the threats to validity, and Section X concludes the paper.

## II Background

### II-A Static Bug Detection

Static bug detection is an automated technique for inspecting and analyzing a program’s source code, object code, or binaries, all without executing the program [^18] [^19]. This process identifies potential bugs by examining how the code’s control and data flow align with specific bug patterns and rules [^20] [^19]. If a code section violates any of these rules, the static bug detector will issue a warning concerning the violated rule for that particular piece of code [^21]. Multiple tools and methods have been created to perform static bug detection within the body of research and industry [^22]. Infer, created by Meta, is a static bug detection tool capable of being utilized across various programming languages, including Java, C, C++, Objective-C, and C#. It accomplishes this by utilizing a predetermined set of rules to identify potential bugs and conducting inter-procedural analysis as part of the project compilation process [^23]. SpotBugs [^24], an enhanced iteration of findBugs [^25] [^26], employs a methodology similar to Infer. It leverages the concept of bug patterns, which consist of specific rules and templates designed to identify particular types of bugs. That being said, applying SpotBugs is limited only to Java byte codes and does not support other languages’ source codes or binaries. Google has also introduced ErrorProne, a static bug detector tailored for Java programs [^27]. ErrorProne is designed to catch common programming errors and potential bugs during compilation. It enhances the compiler’s type analysis, enabling developers to identify more mistakes before advancing to production. In this study, we employ Infer as a baseline for comparison with SkipAnalyzer’s first component and as the tool for generating warnings for our data collection.

### II-B False-Positive Warning Removal

A significant issue associated with the use of static bug detectors is their tendency to generate a considerable volume of inaccurate warnings, which are essentially alerts that are not genuine indicators of actual bugs [^14] [^28] [^29] [^30] [^31] [^32] [^33] [^34]. Recent research demonstrates that the false-positive warning rate can escalate to as high as 91% [^28]. Also, removing high false positive warnings in static analysis tools is very time-consuming for developers since it requires them to verify the generated warnings manually, and it often results in frustration and diminished utilization of these tools [^35] [^36]. Therefore, exploring strategies for reducing false positive warnings in static bug detectors is crucial to increasing the developer’s trust and confidence while using such tools [^36] [^37]. Recent studies have addressed this issue by providing various techniques in detecting and eliminating false-positive warnings. Junker et al. [^38] introduced a method to address false-positive warnings by transforming this issue into a syntactic model-checking problem and employing SMT solvers to evaluate the feasibility of violation of formula in model checking as a counter-example. Wang et al. [^39] have proposed a “Golden Features” set to detect actionable warnings and eliminate the unactionable ones. Hanam et al. [^29] proposed an approach based on machine learning, where they created a warning prediction model to distinguish between actionable and non-actionable warnings. Recently, Kharkar et al. [^14] introduced distinct tools that leverage state-of-the-art neural models, mostly transformer-based models, which are widely regarded as the most effective approach for eliminating false-positive warnings. In this work, we opt to utilize the tools outlined in this study as our baselines for comparison. These tools are referred to as feature-based approach, DeepInferEnhance, and a GPT-C powered approach [^14].

### II-C Automated Program Repair

Automated program repair (APR) techniques have recently garnered significant attention from researchers [^40] [^16] [^9] [^41]. The core concept of program repair is to automatically generate program fixes to facilitate the testing and validation of software systems [^10] [^42]. The APR tools usually take two inputs, a flawed code and a localization of the bug in the flawed code or a description of the program’s expected behaviour [^43]. Automated program repair can be both done dynamically and statically. In the dynamic setting, the localization or description of the bug usually comes in the test suites associated with that flawed code and should be executed to test the validation of the generated patch by the tool [^43] [^9]. As an example, Liu et al. [^1] introduced a method known as Phoenix, which utilizes fix patterns derived from the static analysis of bug violations to generate patches. Their research involved the utilization of the Defects4J benchmark dataset, which includes test suites used to validate the effectiveness of the generated patches for the faulty code. Furthermore, Xia et al. [^9] investigated utilizing Large Language Models (LLMs) for the first time for Automated Program Repair (APR). They examined nine recent and advanced LLMs using five benchmark datasets. All the patches they generated for the faulty codes were validated against the accompanying test suites in their respective datasets. In a static context, the bug’s description or localization is not provided through test suites; instead, it is presented using alternative heuristic or formal methods [^1] [^2] [^44]. For example, Tonder and Goues [^2] proposed an APR technique for fixing general pointer safety properties using Separation Logic [^45]. Bavishi et al. [^1] introduced a method for generating patches and verifying them using a static analyzer as the oracle, eliminating the need for a test suite. Fu et al. [^44] introduced VulRepair, a neural Automated Program Repair (APR) method founded on the CodeT5 model [^46]. Their research involved generating patches for localized bugs found in a pre-existing dataset [^47] [^48]. They evaluated the effectiveness of their approach using a perfect prediction metric and compared the results to the ground truth data within the same dataset.

In this study, we select VulRepair [^44] as our baseline tool to compare with SkipAnalyzer. This choice is made because VulRepair, similar to our approach, does not necessitate the execution of test cases for validation.

### II-D Large Language Models

Large Language Models (LLMs) have gained significant popularity in recent research and industrial applications. Numerous recent studies are investigating the utilization of LLMs in the field of Software Engineering (SE), driven by the significant progress and advancements achieved by LLMs [^41] [^9] [^49]. ChatGPT [^50], one of the most renowned LLMs, has gained widespread recognition recently in performing software engineering tasks [^17] [^9] [^16] [^51]. ChatGPT is accessible throughout an API <sup>2</sup> and has been created by harnessing the capabilities of two state-of-the-art GPT models, specifically, GPT-3.5 Turbo [^52] and GPT-4 [^53]. Utilizing LLMs like ChatGPT as decision making components introduces a novel approach to systematically interact with instruction-tuned LLMs, a method known as prompt engineering. Prompt engineering is the practice of creating tailored input queries that effectively communicate with LLMs [^17] [^16]. Numerous investigations leverage prompt engineering in their utilization of LLMs [^54] [^55] [^56] [^16] [^9]. Prompt engineering as a practice offers the flexibility to utilize various strategies, including the zero-shot approach, where the LLM is prompted without any prior input/output examples; the one-shot method, involving an additional example; and the few-shot strategy, denoted as K-shot, which provides K examples as previous input/output pairs for the LLM [^54] [^17]. Moreover, in prompt engineering, techniques like Chain-of-Thought (COT) are employed to enhance the correctness of generated output. This is achieved by either including the thinking steps in examples or requesting an explanation of the decision-making process from the LLM [^57] [^17] [^58].

## III Data Collection

In this work, we take two types of typical and critical bugs that are targeted by static bug detection, i.e., Null Dereference and Resource Leak as our subjects. To accelerate the data collection, we first applied Infer [^23] to our experimental projects with a focus on detecting Null Dereference and Resource Leak bugs. The rationale behind selecting Infer is its extensive adoption in various companies, including Microsoft. Furthermore, Infer exhibits higher precision in comparison to alternative static analysis tools, leading to the generation of more valid warnings [^14]. We apply Infer to a selection of seven prominent GitHub projects (with at least more than 200 stars), along with three projects featured in prior research, to generate warnings [^14]. These projects are shown in Table I.

TABLE I: Summary of analyzed projects. In this table, projects highlighted in are from a recent study done by Kharkar et al. [^14], and projects highlighted in are the ones we collected from the popular repositories. The warnings reported in this table are generated by Infer [^23] and manually verified.

<table><tbody><tr><td></td><td>Project</td><td>Project Description</td><td>Version</td><td>LOC</td><td>Repository Group</td><td>Number of Verified Warnings</td></tr><tr><td></td><td>nacos</td><td>Dynamic naming and configuration service</td><td>2.0.2</td><td>217,653</td><td>Alibaba</td><td>58</td></tr><tr><td></td><td>azure-maven-plugins</td><td>Maven plugins for Azure services</td><td>2.2.2</td><td>53,025</td><td>Microsoft</td><td>45</td></tr><tr><td></td><td>playwright-java</td><td>Java library to automate Chromium,Firefox, and WebKit with a single API</td><td>1.13.0</td><td>67,548</td><td>Microsoft</td><td>5</td></tr><tr><td></td><td>java-debug</td><td>Java Debug Server, an implementation ofVisual Studio Code (VSCode) Debug Protocol</td><td>0.47.0</td><td>22,852</td><td>Microsoft</td><td>2</td></tr><tr><td></td><td>dolphinscheduler</td><td>Modern data orchestration platform</td><td>2.0.9</td><td>215,808</td><td>Apache</td><td>100</td></tr><tr><td></td><td>dubbo</td><td>high-performance, Java-basedopen-source RPC framework</td><td>3.2</td><td>350,957</td><td>Apache</td><td>193</td></tr><tr><td></td><td>bundletool</td><td>a tool to manipulate Android App Bundlesand Android SDK Bundles</td><td>1.15.1</td><td>135,711</td><td>Google</td><td>51</td></tr><tr><td></td><td>guava</td><td>set of core Java libraries from Googlethat includes new data structures</td><td>32.1.1</td><td>698,201</td><td>Google</td><td>35</td></tr><tr><td></td><td>jreleaser</td><td>release automation tool forJava and non-Java projects</td><td>1.7.0</td><td>114,914</td><td>Community</td><td>30</td></tr><tr><td></td><td>jsoup</td><td>Java library for working withHTML Document Object Model (DOM)</td><td>1.16.1</td><td>33,689</td><td>Community</td><td>33</td></tr><tr><td></td><td colspan="2"></td><td colspan="3">Total Number of Verified Warnings</td><td>552</td></tr></tbody></table>

Note that, as Infer can report false positives [^15] [^14], for each warning, reported, we further manually check whether it is a true bug and not a false positive. This manual labeling process involves three authors with at least four years of development experience, each independently reviewing all the reported warnings by Infer. For each warning, they assign a binary label, i.e., zero indicating a “false positive”, signifying that the warning generated by Infer is incorrect and does not represent a true bug, and one indicating a “true positive”, indicating that the warning is accurate and demonstrates a real bug. Following this individual labeling, the authors then collaborate to identify and resolve any discrepancies or conflicts in their assessments. After resolving these conflicts, we have our comprehensive dataset containing warnings generated by Infer, along with their corresponding ground truth labels. Also, for each of the true bugs, the participants work together to create a patch that can fix the bug.

## IV Approach

Figure 1 provides an overview of SkipAnalyzer’s pipeline, which contains 1) an LLM-based static bug detector that can scan source code and report specific types of bugs (Section IV-A), 2) an LLM-based false positive filter that can identify false-positive bugs in the result of step 1 for improving the detection accuracy (Section IV-B), and 3) an LLM-based patch generator that can generate patches for the detected bugs (Section IV-C).

### IV-A LLM-based Static Bug Detector

In the first component, SkipAnalyzer takes the buggy code snippet as input for in-depth analysis by the LLM. The LLM has been given a specialized prompt with specifications for each bug type to increase its detection validity. For example, to address Null Dereference bugs, we collect common bug patterns for this type of bug, like not having null checks before dereferencing an object. We then provide this information to the LLM in the initial prompt. This specialization helps the LLM understand the task at hand. Additionally, for Resource Leak bugs, a similar approach is used. Moreover, specific structured output requirements are defined to facilitate easy parsing and extracting necessary information from the LLM’s responses. Moreover, the prompt of this component supports adding additional examples to apply one-shot or few-shot strategies. Given that we possess a ground truth for the provided buggy code snippet, we expect SkipAnalyzer to recognize the problem previously identified by Infer and issue a valid warning for it. Furthermore, SkipAnalyzer offers an additional explanation for each potential bug it detects and the warnings it generates.

### IV-B LLM-based False-Positive Warning Filter

In the second component, SkipAnalyzer’s objective is to improve the precision of static bug detection by eliminating false-positive warnings. To achieve this, SkipAnalyzer takes both the buggy code snippet and the warning associated with that code snippet, which is generated by a static bug detector. These warnings can originate from various static bug detectors, such as Infer or SkipAnalyzer itself. Subsequently, the LLM, previously instructed with specialized guidelines, evaluates the buggy code snippet and its corresponding warning. Similar to the first component, the prompt in this stage allow for the inclusion of additional examples, enabling the application of one-shot or few-shot strategies.

### IV-C LLM-based Static Bug Repair

In the third component, SkipAnalyzer processes the buggy code snippet and the warning related to that particular bug in the code. It then proceeds to generate a patch for the buggy code, ultimately producing the fixed version of the code. This component feeds the inputs mentioned above to the LLM, which has previously received tailored instructions on addressing our specific types of bugs. It is worth noting that the prompt of this component does not support additional examples for one-shot or few-shot strategies since examples in our dataset usually have multiple implementations of methods with varying lengths and violate the maximum token limitation of our opted LLMs (more details in Section V-B).

![Refer to caption](https://arxiv.org/html/2310.18532v2/figure/SkipAnalyzer.png)

Fig. 1: The overview of SkipAnalyzer.

## V Experiment Settings

### V-A Research Questions

To evaluate the performance of SkipAnalyzer, we design experiments to answer the following research questions:

RQ1 (Static Bug Detection): What is the performance of SkipAnalyzer in detecting bugs? In this research question, we explore the potential of SkipAnalyzer in the realm of static bug detection. We present the performance of our approach for static bug detection and compare it with our baseline, Infer, while also conducting comparisons under various prompting strategies.

RQ2 (False Positive Warning Removal): What is the effectiveness of SkipAnalyzer in filtering false positive warnings? In this research question, we delve into the effectiveness of SkipAnalyzer’s second component in identifying and eliminating false-positive warnings from the output of a static bug detector. This analysis is applied to both the warnings generated by Infer and those produced in response to RQ1. Eventually, we compare the results of our developed approach with recent state-of-the-art baselines provided by Kharkar et al. [^14] that utilize feature-based and neural models for false-positive warning removal.

RQ3 (Static Bug Repair): What is SkipAnalyzer’s performance in repairing a buggy code for a specific type of bug? This RQ examines the potential of SkipAnalyzer in repairing instances of bugs identified. Note that, as we do not have test cases for the identified bugs, most generate-and-validate program repair techniques cannot be our baselines, as these approaches require a set of test cases as the ground truth. In this work, we choose VulRepair [^44], a CodeT5-based static automated program repair model [^59] that does need test cases as the ground truth.

### V-B ChatGPT Versions

We choose the latest variations of ChatGPT models [^50], ChatGPT-4 [^53] and ChatGPT-3.5 Turbo [^52], as the primary backbone to build SkipAnalyzer. These models have demonstrated strong performance in various software engineering tasks, including code generation, code comprehension, and debugging [^9] [^56]. We interact with these models using OpenAI API <sup>3</sup>. According to the model documentation, there is a wide range of options available for each of the models, and each option comes with its distinct characteristics, including varying token lengths, associated costs, and update frequencies [^50]. For ChatGPT-4 and ChatGPT-3.5 Turbo, we utilize the default settings, which provide maximum token support of 8,192 and 4,097, respectively [^52] [^53]. Due to this limitation in the maximum input token, we constrain the code inputs to the method scope, implying that we only provide the methods themselves as input code snippets to the LLMs.

### V-C Prompting Strategies

In each of the SkipAnalyzer’s components, we use different prompt engineering strategies such as zero-shot, one-shot, and few-shot strategies. In the zero-shot strategy, the LLM is prompted without preceding examples from the previous LLM input and output pairs. In contrast, the few-shot and one-shot strategies incorporate examples from the previous LLM input and output pairs. The difference between the one-shot and few-shot strategies lies in the number of examples included: the one-shot strategy employs a single example in the prompt, while the few-shot strategy encompasses multiple examples. In the first component (LLM-based static bug detector) and the second component (LLM-based false-positive warning filter), we use zero-shot, one-shot, and few-shot strategies. In this paper, for the few-shot strategy, (K-shot), we input the model with three examples (K = 3). The rationale for selecting K = 3 is based on the consideration that opting for values exceeding three could potentially violate the maximum token limit constraint imposed on our inputs for ChatGPT models (details in Section V-B). In the third component (LLM-based bug repair), we only use the zero-shot strategy due to the limitations mentioned in Sections V-B and IV-C. Furthermore, in the prompts for all of SkipAnalyzer’s components, we request the LLM to explain its decision-making process and the steps it takes to arrive at its conclusions. According to the literature, this approach, known as zero-shot Chain-of-Thought reasoning, can enhance the output’s robustness and validity [^57] [^58].

### V-D Data Sampling

Our experiments employ N-fold cross-validation to remove potential data sampling bias, with N set to 5 in this study [^60]. This approach involves splitting the dataset into five subsets, where one-fifth of the data serves as the validation set, and the remaining four-fifths function are used for selecting examples in the process of prompting the LLMs for one-shot and few-shot strategies. We select the examples for these strategies randomly in a uniform distribution. Also, in each of the examples utilized in one-shot and few-shot strategies, we incorporate one instance of a true-positive record and one instance of an false-positive record to prevent any bias towards a particular group of examples when applying these strategies to the LLM.

TABLE II: Summary of SkipAnalyzer’s results for each of the model-strategy combination in Static Bug Detection (RQ1) using two datasets. In this table, rows highlighted in indicate the most effective combination of model and strategy for Null Dereference bugs, and rows in indicate the most effective one for Resource Leak bugs.

| Dataset | Bug Type | Infer’s Precision | Strategy | Model | Accuracy | Precision | Recall | F1-Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | GPT-3.5-Turbo | 50.66% | 52.32% | 40.64% | 45.75% |
|  |  |  | Zero Shot | GPT-4 | 68.37% | 63.76% | 88.93% | 74.27% |
|  |  |  |  | GPT-3.5-Turbo | 60.67% | 62.49% | 59.76% | 61.09% |
|  |  |  | One Shot | GPT-4 | 64.54% | 62.20% | 79.18% | 69.67% |
|  |  |  |  | GPT-3.5-Turbo | 60.47% | 66.14% | 48.63% | 56.05% |
|  | Null Dereference | 50.9% | Few Shot | GPT-4 | 64.31% | 65.21% | 64.96% | 65.09% |
|  |  |  |  | GPT-3.5-Turbo | 56.31% | 44.34% | 40.44% | 42.30% |
|  |  |  | Zero Shot | GPT-4 | 76.95% | 82.73% | 55.11% | 66.15% |
|  |  |  |  | GPT-3.5-Turbo | 34.87% | 35.03% | 72.22% | 47.18% |
|  |  |  | One Shot | GPT-4 | 72.78% | 68.39% | 63.55% | 65.88% |
|  |  |  |  | GPT-3.5-Turbo | 49.31% | 41.49% | 65.55% | 50.82% |
| Our collection | Resource Leak | 39.6% | Few Shot | GPT-4 | 75.25% | 74.12% | 59.55% | 66.04% |
|  |  |  |  | GPT-3.5-Turbo | 50.31% | 69.85% | 41.53% | 52.09% |
|  |  |  | Zero Shot | GPT-4 | 77.90% | 81.87% | 85.51% | 83.65% |
|  |  |  |  | GPT-3.5-Turbo | 58.25% | 70.90% | 59.87% | 64.92% |
|  |  |  | One Shot | GPT-4 | 70.51% | 80.95% | 72.56% | 76.53% |
|  |  |  |  | GPT-3.5-Turbo | 56.47% | 75.60% | 51.28% | 61.11% |
|  | Null Dereference | 65.2% | Few Shot | GPT-4 | 68.52% | 80.57% | 67.56% | 73.50% |
|  |  |  |  | GPT-3.5-Turbo | 61.66% | 50.0% | 50.0% | 50% |
|  |  |  | Zero Shot | GPT-4 | 84.61% | 100% | 71.42% | 83.32% |
|  |  |  |  | GPT-3.5-Turbo | 46.66% | 50% | 70% | 58.33% |
|  |  |  | One Shot | GPT-4 | 73.33% | 60% | 50% | 54.54% |
|  |  |  |  | GPT-3.5-Turbo | 48.33% | 36.66% | 40% | 38.26% |
| Projects from [^14] | Resource Leak | 53.8% | Few Shot | GPT-4 | 68.33% | 60% | 40% | 48% |

### V-E Evaluation Metrics

We employ the following evaluation metrics to assess our experiments concerning each of our research questions:

For Static Bug Detection (RQ1) and False-Positive Warning Removal (RQ2), since we have a ground truth for the warnings we generated for our dataset for evaluation, we use Accuracy, Precision, and Recall metrics. Also, to choose the best combination of strategy and model, we use the F1-score metric. For Static Bug Repair (RQ3), we assess the performance using two key measures that we devised: “Logic Rate”, which signifies the proportion of repaired code with correct logic, and “Syntax Rate”, indicating the proportion of repaired code with correct syntax. To evaluate the “Logic Rate”, we assess correctness by comparing the repaired code to manually crafted ground truth fix patches prepared by our team. In the case of the “Syntax Rate”, we employ a Java parser to validate the syntax of the generated code.

## VI Result Analysis

This section presents the results and answers the research questions we asked in Section V-A.

### VI-A RQ1: Performance of SkipAnalyzer on Static Bug Detection

Approach: In the case of static bug detection, we input the code snippet of each record in our dataset to the SkipAnalyzer’s first component. We expect that SkipAnalyzer will identify the issue previously described and detected by Infer and produce a valid warning. We perform our experiments under different prompting strategies such as zero-shot, one-shot, and few-shot strategies (more details in Section V-C) by using two different ChatGPT models, i.e., ChatGPT-3.5 Turbo and ChatGPT-4 (more details in Section V-B).

Baselines: As a baseline for SkipAnalyzer’s first component, we select Infer, a state-of-the-art static bug detector. Using our collected dataset, we compare SkipAnalyzer’s performance in static bug detection with Infer.

Result: Table II summarizes the results of SkipAnalyzer’s static bug detection task under different prompting strategies with different ChatGPT models using Infer on our collected dataset and the projects used in the prior study by Kharkar et al [^14]. We also show the optimal combination of model and strategy for the static bug detection task for each of the datasets, which is the one that has the highest F1-Score for a specific bug type. Notably, in our collected dataset, the most effective combination for both Null Dereference and Resource Leak bugs involves utilizing ChatGPT-4 in conjunction with the zero-shot strategy. Considering this, in static bug detection, SkipAnalyzer can achieve accuracy, precision, and recall rates of 68.37%, 63.76%, and 88.93%, respectively, for Null Dereference bugs. Likewise, for Resource Leak bugs, these metrics can attain values of 76.95%, 82.73%, and 55.11%, respectively. This indicates that SkipAnalyzer exhibits precision levels that are 12.86% and 43.13% higher than Infer, surpassing the performance of the state-of-the-art static bug detector baseline. Furthermore, it is noteworthy that some other model-strategy combinations also demonstrate superior performance when compared to Infer. For instance, ChatGPT-3.5-Turbo with the one-shot strategy continues to outperform Infer in the detection of Null Dereference bugs, achieving a rate of 62.49% compared to Infer’s 50.9%. We can also see a similar result in the dataset from the projects used by Kharkar et al. [^14]. In this scenario, the most effective strategy and model combination is the zero-shot strategy coupled with the ChatGPT-4 model. Compared to Infer’s base results on this dataset depicted in Table II, we have a 16.6% and 46.2% boost in precision for Null Dereference and Resource Leak bugs, respectively.

<svg id="S6.SS1.p4.pic1" height="129.8" overflow="visible" version="1.1" viewBox="0 0 477.38 129.8" width="477.38"><g style="--ltx-stroke-color:#000000;--ltx-fill-color:#000000;" fill="#000000" stroke="#000000" stroke-width="0.4pt" transform="translate(0,129.8) matrix(1 0 0 -1 0 0)"><g style="--ltx-fill-color:#404040;" fill="#404040" fill-opacity="1.0"><path style="stroke:none" d="M 0 6.23 L 0 123.57 C 0 127.01 2.79 129.8 6.23 129.8 L 471.15 129.8 C 474.59 129.8 477.38 127.01 477.38 123.57 L 477.38 6.23 C 477.38 2.79 474.59 0 471.15 0 L 6.23 0 C 2.79 0 0 2.79 0 6.23 Z"></path></g><g style="--ltx-fill-color:#F2F2F2;" fill="#F2F2F2" fill-opacity="1.0"><path style="stroke:none" d="M 0.69 6.23 L 0.69 123.57 C 0.69 126.63 3.17 129.11 6.23 129.11 L 471.15 129.11 C 474.21 129.11 476.68 126.63 476.68 123.57 L 476.68 6.23 C 476.68 3.17 474.21 0.69 471.15 0.69 L 6.23 0.69 C 3.17 0.69 0.69 3.17 0.69 6.23 Z"></path></g><g fill-opacity="1.0" transform="matrix(1.0 0.0 0.0 1.0 8.99 11.68)"><foreignObject style="--ltx-fo-width:33.2em;--ltx-fo-height:7.89em;--ltx-fo-depth:0.19em;font-size:10pt;" height="111.81" overflow="visible" transform="matrix(1 0 0 -1 0 109.12)" width="459.39"><span id="S6.SS1.p4.pic1.1" style="width:33.2em;"><span id="S6.SS1.p4.pic1.1.1"><span id="S6.SS1.p4.pic1.1.1.1" style="--ltx-fg-color:#000000;">Answer to RQ1: <span id="S6.SS1.p4.pic1.1.1.1.1">SkipAnalyzer can significantly enhance the state-of-the-art static bug detection tool (i.e., Infer) on detecting <span id="S6.SS1.p4.pic1.1.1.1.1.1">Null Dereference</span> and <span id="S6.SS1.p4.pic1.1.1.1.1.2">Resource Leak</span> bugs.</span></span></span></span></foreignObject></g></g></svg>

bugs.

### VI-B RQ2: Performance of SkipAnalyzer on False-Positive Warning Removal

Approach: For answering this RQ, we input both a code snippet and the warning linked to the code snippet generated by a bug detector to SkipAnalyzer. To examine the generalizability of SkipAnalyzer in removing false positives, we use the warnings generated by both Infer and SkipAnalyzer (as described in Section VI-A). We also perform our experiments under different prompting strategies such as zero-shot, one-shot, and few-shot strategies (more details in Section V-B) by using two different ChatGPT models, i.e., ChatGPT-3.5 Turbo and ChatGPT-4 (more details in Section V-B).

Baselines: We select the state-of-the-art false-positive removal approach proposed in the recent study conducted by Kharkar et al. [^14], i.e., GPT-C and also they created two baselines to evaluate GPT-C, which are a feature-based logistic regression model [^14] and DeepInferEnhance (based on CodeBERTa) [^14]. However, the authors neither disclosed the source code for their tool nor their experiments due to confidential issues. They also did not release their collected dataset. Thus, to enable a meaningful comparison with the baseline tools outlined in their study, we gathered data that closely mirrored the one described in their paper, including the same projects and similar versions. Ultimately, we conducted our experiments on a dataset akin to the one they utilized, allowing for a fair and direct comparison between our tool and their baseline tools.

Result: As we explained, we have two options for the static bug detector utilized for false-positive warning removal:

#### VI-B1 Option 1 – Infer

Table III shows the results of applying SkipAnalyzer as a false-positive warning removal tool on warnings generated by Infer and SkipAnalyzer.

TABLE III: Summary of SkipAnalyzer’s results in False-Positive Warning Removal (RQ2) on warnings generated by Infer and SkipAnalyzer. In this table, $\text{P}_{\text{Original}}$ is the precision of the static bug detector for the corresponding bug type and $\text{P}_{\text{After}}$ is the precision of the static bug detector after applying False-Positive Warning Removal process. “Imp.” indicates the amount of precision improvement. Rows highlighted in indicate the most effective combination of model and strategy for Null Dereference bugs, and rows in indicate the most effective one for Resource Leak bugs. Also, the records that have no improvement in precision are shown with “–”.

| Static Bug Detector | Bug Type | Strategy | Model | $\text{P}_{\text{Original}}$ | $\text{P}_{\text{After}}$ | Imp. | Recall | Accuracy | F1-Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  | GPT-3.5-Turbo |  | 40% | \- | 13.07% | 37.91% | 19.71% |
|  |  | Zero Shot | GPT-4 |  | 95% | +29.8 | 27.30% | 51.41% | 42.42% |
|  |  |  | GPT-3.5-Turbo |  | 59.32% | \- | 43.71% | 43.91% | 50.33% |
|  |  | One Shot | GPT-4 |  | 95% | +29.8 | 51.66% | 66.29% | 66.93% |
|  |  |  | GPT-3.5-Turbo |  | 53.63% | \- | 52.17% | 41.40% | 52.89% |
|  | Null Dereference | Few Shot | GPT-4 | 65.2% | 93.88% | +28.68 | 64.23% | 73.46% | 76.27% |
|  |  |  | GPT-3.5-Turbo |  | 63.33% | +9.53 | 80% | 75% | 70.69% |
|  |  | Zero Shot | GPT-4 |  | 60% | +6.2% | 60% | 80% | 60% |
|  |  |  | GPT-3.5-Turbo |  | 40% | \- | 60% | 50% | 48% |
|  |  | One Shot | GPT-4 |  | 60% | +6.2% | 50% | 75% | 54.54% |
|  |  |  | GPT-3.5-Turbo |  | 50% | \- | 80% | 50% | 61.53% |
| Infer | Resource Leak | Few Shot | GPT-4 | 53.8% | 60% | +6.2% | 60% | 80% | 60% |
|  |  |  | GPT-3.5-Turbo |  | 70% | \- | 19.27% | 32.93% | 30.22% |
|  |  | Zero Shot | GPT-4 |  | 86% | +4.13% | 26.72% | 37.45% | 40.78% |
|  |  |  | GPT-3.5-Turbo |  | 67% | \- | 30.72% | 32.72% | 42.26% |
|  |  | One Shot | GPT-4 |  | 97.5% | +15.63 | 52.72% | 59.92% | 68.44% |
|  |  |  | GPT-3.5-Turbo |  | 73.97% | \- | 38.18% | 38.90% | 50.36% |
| SkipAnalyzer | Null Dereference | Few Shot | GPT-4 | 81.87% | 98.18% | +16.31 | 77.45% | 80.25% | 86.59% |

As demonstrated, when dealing with Null Dereference bugs, we can enhance Infer’s precision by 28.68% by employing the zero-shot strategy alongside the ChatGPT-4 model. In the case of Resource Leak bugs, Infer’s precision can be improved by up to 9.53% when utilizing the zero-shot strategy combined with the ChatGPT-3.5-Turbo model. Furthermore, in comparison to the current baselines [^14], as indicated in Table IV, our findings reveal that SkipAnalyzer can surpass the existing baselines in terms of precision improvement, with a margin of at least 11.21% and 3.97% for Null Dereference and Resource Leak bugs, respectively. Also, it is worth noting that Kharkar et al. [^14] did not provide the results of the feature-based logistic regression model and DeepInferEnhance for Resource Leak bugs. Therefore, we specified them with “–” in Table IV.

TABLE IV: Performance of False-Positive Warning Removal of baseline tools proposed by [^14]. In this table column “Precision Imp.” indicates the precision improvement of Infer after applying each of the baseline tools. Also, column “S.A. Recall Imp.” shows SkipAnalyzer ’s improvement in Recall for each bug type compared to the baseline tool.

<table><tbody><tr><td>Baseline</td><td>Bug Type</td><td>Precision Imp.</td><td>Recall</td><td>SA. Recall Imp.</td></tr><tr><td rowspan="2">Feature-based</td><td>Null Dereference</td><td>+8.26%</td><td>65.1%</td><td>+12.35%</td></tr><tr><td>Resource Leak</td><td>–</td><td>–</td><td>–</td></tr><tr><td rowspan="2">DeepInferEnhance</td><td>Null Dereference</td><td>+15.13%</td><td>88.3%</td><td>-10.85%</td></tr><tr><td>Resource Leak</td><td>–</td><td>–</td><td>–</td></tr><tr><td rowspan="2">GPT-C</td><td>Null Dereference</td><td>+17.47%</td><td>83.7%</td><td>-6.25%</td></tr><tr><td>Resource Leak</td><td>+5.56%</td><td>64.5%</td><td>+15.5%</td></tr></tbody></table>

#### VI-B2 Option 2 – SkipAnalyzer

Table III also shows the result of false-positive warning removal on the warnings generated by SkipAnalyzer in Section VI-A. Given that these warnings may arise from various model-strategy combinations, we selected the most effective model-strategy combination for warning generation further to enhance precision through the false-positive warning removal process. Therefore, we opted for the zero-shot strategy with the ChatGPT-4 model.

Moreover, it is worth noting that no false-positive warnings were associated with Resource Leak issues in the warnings generated by this specific model-strategy combination. Consequently, our primary focus remains improving the false-positive warnings related to Null Dereference issues.

As we can see in Table III, by selecting a proper model-strategy combination, which is, in this case, the few-shot strategy with the ChatGPT-4 model, we can improve the precision by removing false-positive warnings of the warnings generated in Section VI-A by 16.31%.

<svg id="S6.SS2.SSS2.p4.pic1" height="79.99" overflow="visible" version="1.1" viewBox="0 0 477.38 79.99" width="477.38"><g style="--ltx-stroke-color:#000000;--ltx-fill-color:#000000;" fill="#000000" stroke="#000000" stroke-width="0.4pt" transform="translate(0,79.99) matrix(1 0 0 -1 0 0)"><g style="--ltx-fill-color:#404040;" fill="#404040" fill-opacity="1.0"><path style="stroke:none" d="M 0 6.23 L 0 73.76 C 0 77.2 2.79 79.99 6.23 79.99 L 471.15 79.99 C 474.59 79.99 477.38 77.2 477.38 73.76 L 477.38 6.23 C 477.38 2.79 474.59 0 471.15 0 L 6.23 0 C 2.79 0 0 2.79 0 6.23 Z"></path></g><g style="--ltx-fill-color:#F2F2F2;" fill="#F2F2F2" fill-opacity="1.0"><path style="stroke:none" d="M 0.69 6.23 L 0.69 73.76 C 0.69 76.82 3.17 79.29 6.23 79.29 L 471.15 79.29 C 474.21 79.29 476.68 76.82 476.68 73.76 L 476.68 6.23 C 476.68 3.17 474.21 0.69 471.15 0.69 L 6.23 0.69 C 3.17 0.69 0.69 3.17 0.69 6.23 Z"></path></g><g fill-opacity="1.0" transform="matrix(1.0 0.0 0.0 1.0 8.99 11.68)"><foreignObject style="--ltx-fo-width:33.2em;--ltx-fo-height:4.29em;--ltx-fo-depth:0.19em;font-size:10pt;" height="62" overflow="visible" transform="matrix(1 0 0 -1 0 59.31)" width="459.39"><span id="S6.SS2.SSS2.p4.pic1.1" style="width:33.2em;"><span id="S6.SS2.SSS2.p4.pic1.1.1"><span id="S6.SS2.SSS2.p4.pic1.1.1.1" style="--ltx-fg-color:#000000;">Answer to RQ2: <span id="S6.SS2.SSS2.p4.pic1.1.1.1.1">SkipAnalyzer can remove false-positive warnings effectively and it outperforms the previous state-of-the-art false-positive warning removal baselines.</span></span></span></span></foreignObject></g></g></svg>

### VI-C RQ3: Performance of SkipAnalyzer on Bug Repair

Approach: For this RQ, we input SkipAnalyzer with the true positive buggy code snippets. We instruct the SkipAnalyzer to understand the code and its corresponding warning and generate a potential patch to repair the buggy code. Subsequently, we manually assess the generated code patches for their syntactical and logical correctness. We perform our experiments under the zero-shot strategy by using two different ChatGPT models, i.e., ChatGPT-3.5 Turbo and ChatGPT-4 (more details in Section V-B). It is important to note that we do not employ the one-shot or few-shot strategy for static bug repair due to the limitations mentioned in Sections IV-C and V-B.

Baselines: We compare the results of our tool with a recent baseline tool called VulRepair [^44]. We used the model and experiment codes offered by the authors to test this baseline tool on our collected dataset. We followed the same configuration for training and evaluating their model on our dataset.

Result: Our research findings indicate that SkipAnalyzer can serve as a robust bug repair tool. Table V displays the performance of SkipAnalyzer in fixing Null Dereference and Resource Leakage bugs for different models. The results reveal that SkipAnalyzer surpasses the baseline tool, VulRepair [^44], with a substantial improvement. Specifically, SkipAnalyzer achieves a logic rate increase of up to 78.91% for Null Dereference bugs and a rate increase of 78.87% for Resource Leak bugs compared to VulRepair. Furthermore, it is worth noting that SkipAnalyzer does not require training or fine-tuning. In contrast, VulRepair mandates the adaptation and training of our dataset for patch generation, showing the superiority of SkipAnalyzer over the recent state-of-the-art baseline tool, VulRepair. Also, VulRepair-generated patches are not self-contained Java codes and should be appended to the buggy code. Hence, they are not parsable, and we specify the Syntax Rate for VulRepair’s generated patches with VI-C in Table V.

TABLE V: Summary of SkipAnalyzer’s results in static bug repair. The “Syntax Rate” column indicates the proportion of generated patches that are syntactically correct. “Logic Rate” column represents the rate of generated patches that are logically correct.

| Bug Type | Model | Logic Rate | Syntax Rate |
| --- | --- | --- | --- |
|  | GPT-3.5-Turbo | 94.25% | 100.0% |
|  | GPT-4 | 97.30% | 99.55% |
| Null Dereference | VulRepair | 18.39% | – |
|  | GPT-3.5-Turbo | 87.11% | 97.77% |
|  | GPT-4 | 91.77% | 97.77% |
| Resource Leak | VulRepair | 12.90% | – |

<svg id="S6.SS3.p4.pic1" height="113.19" overflow="visible" version="1.1" viewBox="0 0 477.38 113.19" width="477.38"><g style="--ltx-stroke-color:#000000;--ltx-fill-color:#000000;" fill="#000000" stroke="#000000" stroke-width="0.4pt" transform="translate(0,113.19) matrix(1 0 0 -1 0 0)"><g style="--ltx-fill-color:#404040;" fill="#404040" fill-opacity="1.0"><path style="stroke:none" d="M 0 6.23 L 0 106.97 C 0 110.41 2.79 113.19 6.23 113.19 L 471.15 113.19 C 474.59 113.19 477.38 110.41 477.38 106.97 L 477.38 6.23 C 477.38 2.79 474.59 0 471.15 0 L 6.23 0 C 2.79 0 0 2.79 0 6.23 Z"></path></g><g style="--ltx-fill-color:#F2F2F2;" fill="#F2F2F2" fill-opacity="1.0"><path style="stroke:none" d="M 0.69 6.23 L 0.69 106.97 C 0.69 110.02 3.17 112.5 6.23 112.5 L 471.15 112.5 C 474.21 112.5 476.68 110.02 476.68 106.97 L 476.68 6.23 C 476.68 3.17 474.21 0.69 471.15 0.69 L 6.23 0.69 C 3.17 0.69 0.69 3.17 0.69 6.23 Z"></path></g><g fill-opacity="1.0" transform="matrix(1.0 0.0 0.0 1.0 8.99 11.68)"><foreignObject style="--ltx-fo-width:33.2em;--ltx-fo-height:6.69em;--ltx-fo-depth:0.19em;font-size:10pt;" height="95.21" overflow="visible" transform="matrix(1 0 0 -1 0 92.52)" width="459.39"><span id="S6.SS3.p4.pic1.1" style="width:33.2em;"><span id="S6.SS3.p4.pic1.1.1"><span id="S6.SS3.p4.pic1.1.1.1" style="--ltx-fg-color:#000000;">Answer to RQ3: <span id="S6.SS3.p4.pic1.1.1.1.1">SkipAnalyzer is effective in patching the detected bugs. In addition, SkipAnalyzer can significantly outperform a recent state-of-the-art baseline tool, i.e., VulRepair.</span></span></span></span></foreignObject></g></g></svg>

## VII Discussions

### VII-A Reasons for Missing Detecting Bugs

SkipAnalyzer also has limitations such as it can miss detecting bugs in RQ1. In this section, we explore the underlying reasons behind the bugs that SkipAnalyzer cannot detect. For our analysis, we first collect all the missing bugs that SkipAnalyzer can not detect. Then, we manually examine all the missing bugs and observe the possible recurring and common patterns among them.

⬇

public DependentParameters getDependency() {

if (this.dependency == null) {

Map<String, Object> taskParamsMap =

JSONUtils.parseObject(this.getTaskParams(), new

TypeReference<Map<String, Object>>() {});

this.dependency = JSONUtils.parseObject((String)

taskParamsMap.get(Constants.DEPENDENCE),

DependentParameters.class);

}

return this.dependency;

}

Ground Truth Warning: object “taskParamsMap” last assigned on line 3 could be null and is dereferenced at line 7.

SkipAnalyzer’s Explanation: The code checks if “this.dependency” is null before assigning a value to it. Therefore, there is no potential null dereference bug in this code.

Fig. 2: An example of a missing Null Dereference.

⬇

private static void registerContextBeans(ConfigurableListableBeanFactory

beanFactory, DubboSpringInitContext context) {

registerSingleton(beanFactory, context);

registerSingleton(beanFactory,

context.getApplicationModel());

registerSingleton(beanFactory,

context.getModuleModel());

}

Ground Truth Warning: object returned by “context.getApplicationModel()” could be null and is dereferenced by call to “registerSingleton(…)” at line 6.

SkipAnalyzer’s Explanation: The values of “context.getApplicationModel()” and “context.getModuleModel()” are being checked for null before being registered as singletons, so there is no null dereference bug in this code.

Fig. 3: An example of a missing Null Dereference bug by SkipAnalyzer. In this case, the “registerSingleton” is a function declared as outside of the method where the Null Dereference is detected. Consequently, SkipAnalyzer attempts to establish a connection between the registering for singleton and the Null Dereference issue, even though they are not directly related.

#### VII-A1 Null Dereference

We have identified three patterns from Null Dereference bugs that SkipAnalyzer missed. Firstly, SkipAnalyzer struggles to distinguish Null Dereferences of objects within a null check for another object. This is often observed when SkipAnalyzer overlooks objects that might become null and dereferenced later within a null check for another object. This issue becomes more pronounced when these objects have some form of relationship with one another, such as when the first object serves as an argument to a method call of the second object. Figure 2 shows an example bug that is missing by SkipAnalyzer.

Second, we have observed that SkipAnalyzer sometimes makes random assumptions about the method, API call, class variable, and instance variable that are usually outside the current method’s scope. SkipAnalyzer’s inability to access the implementation details of these entities hinders its ability to determine whether they can return null or not. Consequently, SkipAnalyzer occasionally makes incorrect assumptions about the return values of such entities, leading to missing potential Null Dereference bugs. Figure 3 shows an example bug that cannot be detected by SkipAnalyzer because of the above reason.

Third, another prevalent pattern is SkipAnalyzer’s difficulty in detecting Null Dereferences that occur in a single line through a chain of method invocations. While SkipAnalyzer may be able to detect the first object invoking a method, it often fails to identify the subsequent methods chained through method calls to the initial object, which could also return null. As an example, we can look at Figure 4.

⬇

private void cacheNormalInvokers(BitList<Invoker\<T>>

invokers) {

BitList<Invoker\<T>> clonedInvokers = invokers.clone();

clonedInvokers.removeIf((invoker) ->

invoker.getUrl().getProtocol().equals(MOCK\_PROTOCOL));

normalInvokers = clonedInvokers;

}

Ground Truth Warning: object returned by “invoker.getUrl().getProtocol()” could be null and is dereferenced at line 5.

SkipAnalyzer’s Explanation: The ‘normalInvokers‘ object is assigned the value of ‘clonedInvokers‘, which is a cloned version of ‘invokers‘. However, there is no null check for ‘clonedInvokers‘ before assigning it to ‘normalInvokers‘. If ‘invokers.clone()‘ returns null, it will result in a null dereference bug.

Fig. 4: An example of a missing Null Dereference bug by SkipAnalyzer. In this example, SkipAnalyzer missed the Null Dereference issue in the method call chain and did not report anything about it.

#### VII-A2 Resource Leak

The prevalent pattern of overlooked Resource Leak bugs involves cases where the code partially handles the release of resources. This implies that while some resources are properly released after their use, there are still other resources that remain unreleased. Figure 5 is an example of a missing Resource Leak bug due to this issue.

⬇

private void executeForSdkArchive() {

try (TempDirectory tempDir = new

TempDirectory(getClass().getSimpleName());

ZipFile asarZip = new

ZipFile(getSdkArchivePath().get().toFile())) {

Path modulesPath =

tempDir.getPath().resolve(EXTRACTED\_SDK);

try (ZipFile modulesZip = getModulesZip(asarZip,

modulesPath)) {

SdkAsarValidator.validateModulesFile(modulesZip);

SdkAsar sdkAsar = SdkAsar.buildFromZip(asarZip,

modulesZip, modulesPath);

generateAppApks(sdkAsar.getModule(), tempDir);

}

} catch (ZipException e) {

throw CommandExecutionException.builder()

.withInternalMessage(”ASAR is not a valid zip file.”)

.withCause(e)

.build();

} catch (IOException e) {

throw new UncheckedIOException(”An error occurred when

processing the SDK archive.”, e);

}

}

Ground Truth Warning: resource of type “java.util.zip.ZipFile” acquired by call to “ZipFile(…)” at line 4 is not released after line 20.

SkipAnalyzer’s Explanation: The resources “tempDir” and “asarZip” are allocated using the try-with-resources syntax, which means they will be automatically released and closed after the try block finishes. Therefore, there is no resource leakage bug in this code.

Fig. 5: An example of a missing Resource Leak bug by SkipAnalyzer. In this example, Although SkipAnalyzer correctly identify “tempDir” as not buggy, it cannot detect the “asarZip”, which is an actual Resource Leak bug. The code does not use Java 7 try-with-resources (try(…)) syntax for the “asarZip” object. It only uses it for “tempDir” and also “modulesZip” in the next lines.

## VIII Threats to Validity

In this research, our focus is solely on Java projects, and we do not consider projects developed in other programming languages. This choice stems from the limitation that Infer, the tool we employ for generating warnings and the dataset, is not capable of handling multiple programming languages. However, it is worth noting that Infer can be used with languages like C and C#. Therefore, conducting a similar analysis on additional languages that Infer is compatible with can contribute to the validity of our research.

Another potential challenge to the validity of our work is that the evaluation is conducted exclusively on a dataset created from warnings generated by Infer, without taking into account warnings generated by alternative static analysis tools like SpotBugs [^24] or Error-Prone [^27]. In this study, we opted not to include SpotBugs and Error-Prone as static bug detectors. This decision was made because these tools categorize bug types differently, and we aimed to maintain consistency in our bug classification [^15]. Additionally, Infer has better precision and outperforms them in accuracy [^14].

Also, we exclusively employed LLM models from OpenAI, specifically ChatGPT-4 and ChatGPT-3.5 Turbo. It is essential to recognize that other companies have also introduced their LLM models, such as Meta’s Llama2 and Google’s PaLM2 and Bard. These alternative models may bring their own unique features and performance characteristics, which could potentially impact the validity of our findings.

Furthermore, it is important to acknowledge that the performance of our SkipAnalyzer may exhibit variations across different sets of projects. To account for this variability and enhance the generalizability of our results, we have included a diverse array of projects from various repositories and backgrounds.

## IX Related Work

### IX-A LLM Applications in Software Engineering

Recently, there has been a considerable volume of research dedicated to exploring the capabilities of Large Language Models (LLMs) within the domain of Software Engineering (SE). For example, several studies focus on automated program repair [^9] [^41] [^61] [^62] [^63] [^64] [^44] [^65] [^16] [^66] [^67]. For instance, Xia et al. [^9] conducted the first empirical study to evaluate nine recent state-of-the-art LLMs for automated program repair tasks on five different repair datasets. Mashhadi and Hemmati [^67] fine-tuned a repair dataset of single-line Java bugs on the CodeBERT model. Also, numerous studies in software testing and fuzzing utilize LLMs [^54] [^68] [^69] [^70]. For example, Deng et al. [^69] proposed FuzzGPT, a novel LLM-based fuzzer that can produce unusual programs for fuzzing real-world systems. The same authors also provide TitanFuzz [^70], the first LLM-based approach for fuzzing Deep Learning (DL) libraries. Kang et al. [^54] proposed LIBRO, a framework that uses LLMs to automate test generation from general bug reports. Furthermore, there are studies that focus on Oracle generation [^71] [^72] [^73]. For example, Tufano et al. [^71] proposed a novel assertion generation approach using a BART transformer model. Nie et al. [^72] proposed an approach for predicting the next statement in test methods that need reasoning about the code execution by utilizing CodeT5 model. Dinella et al. [^73] introduced TOGA, a neural transformer-based method for inferring both exceptional and assertion test conditions by considering the context of the main method. Also, there are studies that focus on mobile applications such as Android. [^17] [^74]. Feng et al. [^17] introduced an automated technique for Android bug reproduction, utilizing ChatGPT-3.5 to extract reproducible steps and automate the bug replay procedure. Taeb et al. [^74] proposed an automated approach for producing a navigable video from a manual accessibility test of a mobile application by utilizing ChatGPT-4.

## X Conclusion

This paper introduces a novel LLM-based tool for static code analysis. Our developed tool, SkipAnalyzer, can showcase the capabilities of LLMs like ChatGPT models in carrying out code analysis tasks, including static bug detection, false-positive warning removal, and bug repair. To generate warnings, we employed Infer, a well-established static analysis tool, on prominent open-source Java projects and projects from prior research. Subsequently, we meticulously labeled each of the generated warnings for two types of bugs: Null Dereference and Resource Leak, thereby creating a new dataset for our analytical work. We then harnessed the power of different ChatGPT models (i.e., ChatGPT-3.5 Turbo, ChatGPT-4) under different prompting strategies. Our experiments reveal that SkipAnalyzer’s components can outperform baseline counterparts, all while offering significant advantages in terms of reduced costs and complexity.

In the future, our research endeavors will broaden in scope as we aim to explore a wider array of Large Language Models (LLMs), such as Meta’s Llama, Google’s Bard, and PaLM2, and integrate them into SkipAnalyzer. We also intend to delve into a comparative analysis between fine-tuned LLMs and LLMs that are specialized for specific tasks through prompt engineering. Additionally, we find it intriguing to assess SkipAnalyzer’s performance on different types of bugs. Furthermore, adding additional components to SkipAnalyzer to further examine coding practices and styles would be helpful.

[^1]: R. Bavishi, H. Yoshida, and M. R. Prasad, “Phoenix: Automated data-driven synthesis of repairs for static analysis violations,” in *Proceedings of the 2019 27th ACM Joint Meeting on European Software Engineering Conference and Symposium on the Foundations of Software Engineering*, 2019, pp. 613–624.

[^2]: R. van Tonder and C. L. Goues, “Static automated program repair for heap properties,” in *Proceedings of the 40th International Conference on Software Engineering*, 2018, pp. 151–162.

[^3]: K. Liu, A. Koyuncu, D. Kim, and T. F. Bissyandè, “Avatar: Fixing semantic bugs with fix patterns of static analysis violations,” in *2019 IEEE 26th International Conference on Software Analysis, Evolution and Reengineering (SANER)*, 2019, pp. 1–12.

[^4]: D. Marcilio, R. Bonifácio, E. Monteiro, E. Canedo, W. Luz, and G. Pinto, “Are static analysis violations really fixed? a closer look at realistic usage of sonarqube,” in *2019 IEEE/ACM 27th International Conference on Program Comprehension (ICPC)*, 2019, pp. 209–219.

[^5]: A. Carvalho, W. Luz, D. Marcílio, R. Bonifácio, G. Pinto, and E. Dias Canedo, “C-3pr: A bot for fixing static analysis violations via pull requests,” in *2020 IEEE 27th International Conference on Software Analysis, Evolution and Reengineering (SANER)*, 2020, pp. 161–171.

[^6]: S. Afrose, Y. Xiao, S. Rahaman, B. P. Miller, and D. Yao, “Evaluation of static vulnerability detection tools with java cryptographic api benchmarks,” *IEEE Transactions on Software Engineering*, vol. 49, no. 2, pp. 485–497, 2023.

[^7]: S. Lipp, S. Banescu, and A. Pretschner, “An empirical study on the effectiveness of static c code analyzers for vulnerability detection,” in *Proceedings of the 31st ACM SIGSOFT International Symposium on Software Testing and Analysis*, ser. ISSTA 2022. New York, NY, USA: Association for Computing Machinery, 2022, p. 544–555. \[Online\]. Available: [https://doi.org/10.1145/3533767.3534380](https://doi.org/10.1145/3533767.3534380)

[^8]: Y. Pan, X. Ge, C. Fang, and Y. Fan, “A systematic literature review of android malware detection using static analysis,” *IEEE Access*, vol. 8, pp. 116 363–116 379, 2020.

[^9]: C. S. Xia, Y. Wei, and L. Zhang, “Automated program repair in the era of large pre-trained language models,” in *Proceedings of the 45th International Conference on Software Engineering*, ser. ICSE ’23. IEEE Press, 2023, p. 1482–1494. \[Online\]. Available: [https://doi.org/10.1109/ICSE48619.2023.00129](https://doi.org/10.1109/ICSE48619.2023.00129)

[^10]: L. Gazzola, D. Micucci, and L. Mariani, “Automatic software repair: A survey,” in *Proceedings of the 40th International Conference on Software Engineering*, 2018, pp. 1219–1219.

[^11]: G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, and A. Anandkumar, “Voyager: An open-ended embodied agent with large language models,” *arXiv preprint arXiv:2305.16291*, 2023.

[^12]: C. H. Song, J. Wu, C. Washington, B. M. Sadler, W.-L. Chao, and Y. Su, “Llm-planner: Few-shot grounded planning for embodied agents with large language models,” in *Proceedings of the IEEE/CVF International Conference on Computer Vision*, 2023, pp. 2998–3009.

[^13]: X. Hou, Y. Zhao, Y. Liu, Z. Yang, K. Wang, L. Li, X. Luo, D. Lo, J. Grundy, and H. Wang, “Large language models for software engineering: A systematic literature review,” *arXiv preprint arXiv:2308.10620*, 2023.

[^14]: A. Kharkar, R. Z. Moghaddam, M. Jin, X. Liu, X. Shi, C. Clement, and N. Sundaresan, “Learning to reduce false positives in analytic bug detectors,” in *Proceedings of the 44th International Conference on Software Engineering*, 2022, pp. 1307–1316.

[^15]: N. S. Harzevili, J. Shin, J. Wang, and S. Wang, “Characterizing and understanding software security vulnerabilities in machine learning libraries,” *arXiv preprint arXiv:2203.06502*, 2022.

[^16]: J. Cao, M. Li, M. Wen, and S.-c. Cheung, “A study on prompt design, advantages and limitations of chatgpt for deep learning program repair,” *arXiv preprint arXiv:2304.08191*, 2023.

[^17]: S. Feng and C. Chen, “Prompting is all your need: Automated android bug replay with large language models,” *arXiv preprint arXiv:2306.01987*, 2023.

[^18]: L. Li, T. F. Bissyandé, M. Papadakis, S. Rasthofer, A. Bartel, D. Octeau, J. Klein, and L. Traon, “Static analysis of android apps: A systematic literature review,” *Information and Software Technology*, vol. 88, pp. 67–95, 2017.

[^19]: Q. Ashfaq, R. Khan, and S. Farooq, “A comparative analysis of static code analysis tools that check java code adherence to java coding standards,” in *2019 2nd International Conference on Communication, Computing and Digital systems (C-CODE)*. IEEE, 2019, pp. 98–103.

[^20]: C. Vassallo, S. Panichella, F. Palomba, S. Proksch, H. C. Gall, and A. Zaidman, “How developers engage with static analysis tools in different contexts,” *Empirical Software Engineering*, vol. 25, pp. 1419–1457, 2020.

[^21]: D. A. Tomassi and C. Rubio-González, “On the real-world effectiveness of static bug detectors at finding null pointer exceptions,” in *2021 36th IEEE/ACM International Conference on Automated Software Engineering (ASE)*, 2021, pp. 292–303.

[^22]: N. S. Harzevili *et al.*, “Automatic static bug detection for machine learning libraries: Are we there yet?” *ArXiv*, 2023, accessed 18 Oct. 2023. \[Online\]. Available: [https://arxiv.org/abs/2307.04080](https://arxiv.org/abs/2307.04080)

[^23]: Infer. Infer official website. \[Online\]. Available: [https://fbinfer.com/](https://fbinfer.com/)

[^24]: D. A. Tomassi, “Bugs in the wild: Examining the effectiveness of static analyzers at finding real-world bugs,” in *Proceedings of the 2018 26th ACM Joint Meeting on European Software Engineering Conference and Symposium on the Foundations of Software Engineering*, ser. ESEC/FSE 2018. New York, NY, USA: Association for Computing Machinery, 2018, p. 980–982.

[^25]: D. Hovemeyer and W. Pugh, “Finding bugs is easy,” *SIGPLAN Not.*, vol. 39, no. 12, p. 92–106, dec 2004. \[Online\]. Available: [https://doi.org/10.1145/1052883.1052895](https://doi.org/10.1145/1052883.1052895)

[^26]: B. Cole, D. Hakim, D. Hovemeyer, R. Lazarus, W. Pugh, and K. Stephens, “Improving your software using static analysis to find bugs,” in *Companion to the 21st ACM SIGPLAN Symposium on Object-Oriented Programming Systems, Languages, and Applications*, ser. OOPSLA ’06. New York, NY, USA: Association for Computing Machinery, 2006, p. 673–674. \[Online\]. Available: [https://doi.org/10.1145/1176617.1176667](https://doi.org/10.1145/1176617.1176667)

[^27]: Google. (2023) Errorprone. Accessed on Date. \[Online\]. Available: [https://errorprone.info/index](https://errorprone.info/index)

[^28]: H. J. Kang, K. L. Aw, and D. Lo, “Detecting false alarms from automatic static analysis tools: How far are we?” in *Proceedings of the 44th International Conference on Software Engineering*, ser. ICSE ’22. New York, NY, USA: Association for Computing Machinery, 2022, p. 698–709.

[^29]: Q. Hanam, L. Tan, R. Holmes, and P. Lam, “Finding patterns in static analysis alerts: Improving actionable alert ranking,” in *Proceedings of the 11th Working Conference on Mining Software Repositories*, ser. MSR 2014. New York, NY, USA: Association for Computing Machinery, 2014, p. 152–161. \[Online\]. Available: [https://doi.org/10.1145/2597073.2597100](https://doi.org/10.1145/2597073.2597100)

[^30]: X. Yang, J. Chen, R. Yedida, Z. Yu, and T. Menzies, “Learning to recognize actionable static code warnings (is intrinsically easy),” *Empirical Softw. Engg.*, vol. 26, no. 3, may 2021. \[Online\]. Available: [https://doi.org/10.1007/s10664-021-09948-6](https://doi.org/10.1007/s10664-021-09948-6)

[^31]: H. Shen, J. Fang, and J. Zhao, “Efindbugs: Effective error ranking for findbugs,” in *2011 Fourth IEEE International Conference on Software Testing, Verification and Validation*, 2011, pp. 299–308.

[^32]: Z. P. Reynolds, A. B. Jayanth, U. Koc, A. A. Porter, R. R. Raje, and J. H. Hill, “Identifying and documenting false positive patterns generated by static code analysis tools,” in *2017 IEEE/ACM 4th International Workshop on Software Engineering Research and Industrial Practice (SER&IP)*, 2017, pp. 55–61.

[^33]: T. Muske and A. Serebrenik, “Techniques for efficient automated elimination of false positives,” in *2020 IEEE 20th International Working Conference on Source Code Analysis and Manipulation (SCAM)*, 2020, pp. 259–263.

[^34]: S. Heckman and L. Williams, “A systematic literature review of actionable alert identification techniques for automated static code analysis,” *Information and Software Technology*, vol. 53, no. 4, pp. 363–387, 2011.

[^35]: M. Christakis and C. Bird, “What developers want and need from program analysis: an empirical study,” in *Proceedings of the 31st IEEE/ACM international conference on automated software engineering*, 2016, pp. 332–343.

[^36]: B. Johnson, Y. Song, E. Murphy-Hill, and R. Bowdidge, “Why don’t software developers use static analysis tools to find bugs?” in *2013 35th International Conference on Software Engineering (ICSE)*, 2013, pp. 672–681.

[^37]: U. Koc, S. Wei, J. S. Foster, M. Carpuat, and A. A. Porter, “An empirical assessment of machine learning approaches for triaging reports of a java static analysis tool,” in *2019 12th ieee conference on software testing, validation and verification (icst)*. IEEE, 2019, pp. 288–299.

[^38]: M. Junker, R. Huuck, A. Fehnker, and A. Knapp, “Smt-based false positive elimination in static program analysis,” in *Formal Methods and Software Engineering: 14th International Conference on Formal Engineering Methods, ICFEM 2012, Kyoto, Japan, November 12-16, 2012. Proceedings 14*. Springer, 2012, pp. 316–331.

[^39]: J. Wang, S. Wang, and Q. Wang, “Is there a ”golden” feature set for static warning identification? an experimental evaluation,” in *Proceedings of the 12th ACM/IEEE International Symposium on Empirical Software Engineering and Measurement*, ser. ESEM ’18. New York, NY, USA: Association for Computing Machinery, 2018.

[^40]: A. Arcuri, “On the automation of fixing software bugs,” in *Companion of the 30th International Conference on Software Engineering*, ser. ICSE Companion ’08. New York, NY, USA: Association for Computing Machinery, 2008, p. 1003–1006. \[Online\]. Available: [https://doi.org/10.1145/1370175.1370223](https://doi.org/10.1145/1370175.1370223)

[^41]: Z. Fan, X. Gao, A. Roychoudhury, and S. H. Tan, “Improving automatically generated code from codex via automated program repair,” *arXiv preprint arXiv:2205.10583*, 2022.

[^42]: W. Weimer, T. Nguyen, C. Le Goues, and S. Forrest, “Automatically finding patches using genetic programming,” in *2009 IEEE 31st International Conference on Software Engineering*. IEEE, 2009, pp. 364–374.

[^43]: A. Nilizadeh, G. T. Leavens, X.-B. D. Le, C. S. Păsăreanu, and D. R. Cok, “Exploring true test overfitting in dynamic automated program repair using formal methods,” in *2021 14th IEEE Conference on Software Testing, Verification and Validation (ICST)*, 2021, pp. 229–240.

[^44]: M. Fu, C. Tantithamthavorn, T. Le, V. Nguyen, and D. Phung, “Vulrepair: A t5-based automated software vulnerability repair,” in *Proceedings of the 30th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering*, ser. ESEC/FSE 2022. New York, NY, USA: Association for Computing Machinery, 2022, p. 935–947. \[Online\]. Available: [https://doi.org/10.1145/3540250.3549098](https://doi.org/10.1145/3540250.3549098)

[^45]: J. Berdine, A. Cox, S. Ishtiaq, and C. M. Wintersteiger, “Diagnosing abstraction failure for separation logic–based analyses,” in *Computer Aided Verification*, P. Madhusudan and S. A. Seshia, Eds. Berlin, Heidelberg: Springer Berlin Heidelberg, 2012, pp. 155–173.

[^46]: Y. Wang, W. Wang, S. Joty, and S. C. Hoi, “CodeT5: Identifier-aware unified pre-trained encoder-decoder models for code understanding and generation,” in *Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing*. Online and Punta Cana, Dominican Republic: Association for Computational Linguistics, Nov. 2021, pp. 8696–8708.

[^47]: J. Fan, Y. Li, S. Wang, and T. N. Nguyen, “A c/c++ code vulnerability dataset with code changes and cve summaries,” in *Proceedings of the 17th International Conference on Mining Software Repositories*, ser. MSR ’20. New York, NY, USA: Association for Computing Machinery, 2020, p. 508–512.

[^48]: G. Bhandari, A. Naseer, and L. Moonen, “Cvefixes: Automated collection of vulnerabilities and their fixes from open-source software,” in *Proceedings of the 17th International Conference on Predictive Models and Data Analytics in Software Engineering*, ser. PROMISE 2021. New York, NY, USA: Association for Computing Machinery, 2021, p. 30–39.

[^49]: Z. Zeng, H. Tan, H. Zhang, J. Li, Y. Zhang, and L. Zhang, “An extensive study on pre-trained models for program understanding and generation,” in *Proceedings of the 31st ACM SIGSOFT international symposium on software testing and analysis*, 2022, pp. 39–51.

[^50]: OpenAI. (2023) Chatgpt. Accessed on Date. \[Online\]. Available: [https://openai.com/blog/chatgpt](https://openai.com/blog/chatgpt)

[^51]: Q. Guo and et al., “Exploring the potential of chatgpt in automated code refinement: An empirical study,” *arXiv*, 2023, accessed 19 Oct. 2023. \[Online\]. Available: [https://arxiv.org/abs/2309.08221](https://arxiv.org/abs/2309.08221)

[^52]: OpenAI. (2023) Chatgpt-3.5. Accessed on Date. \[Online\]. Available: [https://platform.openai.com/docs/models/gpt-3-5](https://platform.openai.com/docs/models/gpt-3-5)

[^53]: “Gpt-4 technical report,” ArXiv, 2023, accessed 17 Oct. 2023. \[Online\]. Available: [https://arxiv.org/abs/2303.08774](https://arxiv.org/abs/2303.08774)

[^54]: S. Kang, J. Yoon, and S. Yoo, “Large language models are few-shot testers: Exploring llm-based general bug reproduction,” in *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)*. IEEE, 2023, pp. 2312–2323.

[^55]: D. Zan, B. Chen, F. Zhang, D. Lu, B. Wu, B. Guan, W. Yongji, and J.-G. Lou, “Large language models meet NL2Code: A survey,” in *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*. Toronto, Canada: Association for Computational Linguistics, Jul. 2023, pp. 7443–7464.

[^56]: B. Min, H. Ross, E. Sulem, A. P. B. Veyseh, T. H. Nguyen, O. Sainz, E. Agirre, I. Heintz, and D. Roth, “Recent advances in natural language processing via large pre-trained language models: A survey,” *ACM Comput. Surv.*, vol. 56, no. 2, sep 2023.

[^57]: J. Wei and et al., “Chain-of-thought prompting elicits reasoning in large language models,” *arXiv*, 2022, accessed 19 Oct. 2023.

[^58]: T. Kojima, S. S. Gu, M. Reid, Y. Matsuo, and Y. Iwasawa, “Large language models are zero-shot reasoners,” in *Advances in Neural Information Processing Systems*, S. Koyejo, S. Mohamed, A. Agarwal, D. Belgrave, K. Cho, and A. Oh, Eds., vol. 35. Curran Associates, Inc., 2022, pp. 22 199–22 213.

[^59]: Y. Wang, W. Wang, S. Joty, and S. C. Hoi, “Codet5: Identifier-aware unified pre-trained encoder-decoder models for code understanding and generation,” *arXiv preprint arXiv:2109.00859*, 2021.

[^60]: T.-T. Wong and P.-Y. Yeh, “Reliable accuracy estimates from k-fold cross validation,” *IEEE Transactions on Knowledge and Data Engineering*, vol. 32, no. 8, pp. 1586–1594, 2020.

[^61]: H. Joshi, J. Cambronero Sanchez, S. Gulwani, V. Le, G. Verbruggen, and I. Radiček, “Repair is nearly generation: Multilingual program repair with llms,” *Proceedings of the AAAI Conference on Artificial Intelligence*, vol. 37, no. 4, pp. 5131–5140, Jun. 2023.

[^62]: M. Jin, S. Shahriar, M. Tufano, X. Shi, S. Lu, N. Sundaresan, and A. Svyatkovskiy, “Inferfix: End-to-end program repair with llms,” *arXiv preprint arXiv:2303.07263*, 2023.

[^63]: Z. Fan, X. Gao, M. Mirchev, A. Roychoudhury, and S. H. Tan, “Automated repair of programs from large language models,” in *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)*, 2023, pp. 1469–1481.

[^64]: F. Ribeiro, “Large language models for automated program repair,” in *Companion Proceedings of the 2023 ACM SIGPLAN International Conference on Systems, Programming, Languages, and Applications: Software for Humanity*, ser. SPLASH 2023. New York, NY, USA: Association for Computing Machinery, 2023, p. 7–9.

[^65]: N. Jiang, K. Liu, T. Lutellier, and L. Tan, “Impact of code language models on automated program repair,” in *Proceedings of the 45th International Conference on Software Engineering*, ser. ICSE ’23. IEEE Press, 2023, p. 1430–1442.

[^66]: C. S. Xia and L. Zhang, “Less training, more repairing please: Revisiting automated program repair via zero-shot learning,” in *Proceedings of the 30th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering*, ser. ESEC/FSE 2022. New York, NY, USA: Association for Computing Machinery, 2022, p. 959–971. \[Online\]. Available: [https://doi.org/10.1145/3540250.3549101](https://doi.org/10.1145/3540250.3549101)

[^67]: E. Mashhadi and H. Hemmati, “Applying codebert for automated program repair of java simple bugs,” in *2021 IEEE/ACM 18th International Conference on Mining Software Repositories (MSR)*, 2021, pp. 505–509.

[^68]: C. Lemieux, J. P. Inala, S. K. Lahiri, and S. Sen, “Codamosa: Escaping coverage plateaus in test generation with pre-trained large language models,” in *Proceedings of the 45th International Conference on Software Engineering*, ser. ICSE ’23. IEEE Press, 2023, p. 919–931. \[Online\]. Available: [https://doi.org/10.1109/ICSE48619.2023.00085](https://doi.org/10.1109/ICSE48619.2023.00085)

[^69]: Y. Deng, C. S. Xia, C. Yang, S. D. Zhang, S. Yang, and L. Zhang, “Large language models are edge-case fuzzers: Testing deep learning libraries via fuzzgpt,” *arXiv preprint arXiv:2304.02014*, 2023.

[^70]: Y. Deng, C. S. Xia, H. Peng, C. Yang, and L. Zhang, “Fuzzing deep-learning libraries via large language models,” *arXiv preprint arXiv:2212.14834*, 2022.

[^71]: M. Tufano, D. Drain, A. Svyatkovskiy, and N. Sundaresan, “Generating accurate assert statements for unit test cases using pretrained transformers,” in *Proceedings of the 3rd ACM/IEEE International Conference on Automation of Software Test*, ser. AST ’22. New York, NY, USA: Association for Computing Machinery, 2022, p. 54–64. \[Online\]. Available: [https://doi.org/10.1145/3524481.3527220](https://doi.org/10.1145/3524481.3527220)

[^72]: P. Nie, R. Banerjee, J. J. Li, R. J. Mooney, and M. Gligoric, “Learning deep semantics for test completion,” *arXiv preprint arXiv:2302.10166*, 2023.

[^73]: E. Dinella, G. Ryan, T. Mytkowicz, and S. K. Lahiri, “Toga: A neural method for test oracle generation,” in *Proceedings of the 44th International Conference on Software Engineering*, ser. ICSE ’22. New York, NY, USA: Association for Computing Machinery, 2022, p. 2130–2141. \[Online\]. Available: [https://doi.org/10.1145/3510003.3510141](https://doi.org/10.1145/3510003.3510141)

[^74]: M. Taeb, A. Swearngin, E. School, R. Cheng, Y. Jiang, and J. Nichols, “Axnav: Replaying accessibility tests from natural language,” *arXiv preprint arXiv:2310.02424*, 2023.