# Generative AI Exposure and Financial Analyst Employment and Wages

Miguel Ferguson II

## Introduction and research question

Generative artificial intelligence (GenAI) refers here to systems that produce new text, code, or other content in response to prompts. Financial analysts can use these systems to summarize filings, draft commentary, and assist with coding or analysis. An occupation’s GenAI exposure is the estimated share of its tasks that such systems could help perform; it measures technical potential, not whether an employer has adopted the technology or replaced a worker (Eloundou et al., 2024). Exposure could reduce demand for some tasks while making analysts more productive in others. Evidence of faster writing with GenAI, for example, does not by itself establish a change in hiring or pay (Noy & Zhang, 2023).

This proposal asks whether U.S. occupations with greater measured GenAI exposure experienced different employment and wage changes after the late-2022 public release of ChatGPT. The study will compare occupations with different exposure scores within the same industry and year, then describe how analyst outcomes compare with selected finance occupations. Its contribution is an early, transparent test of whether predicted task exposure appears in official labor outcomes. Because exposure is not adopted and the data have time-series limitations, the findings will be framed as associations rather than proof of displacement or augmentation.

## Background and proposed comparison

Task-based research explains why the direction of a technology’s labor effect cannot be inferred from its capabilities alone: automation can replace tasks, while new or complementary tasks can support labor demand (Autor et al., 2003; Acemoglu & Restrepo, 2019). Eloundou et al. (2024) estimate which occupational tasks large language models could affect. Their measure is a forecast of potential task change. Noy and Zhang (2023) document productivity effects in professional writing tasks, a narrower outcome than employment or wages. Together, these studies motivate an outcome test rather than an assumption that exposure equals job loss.

I will attach a predetermined exposure score to each occupation in Bureau of Labor Statistics Occupational Employment and Wage Statistics (OEWS) data. I will then estimate whether employment and wages changed more after 2022 for high-exposure occupations than for lower-exposure occupations operating in the same industry. For example, if two occupations are observed in banking in 2024, the comparison uses their difference in exposure and their respective changes from the pre-period. Industry-by-year effects account for broad banking conditions shared by both. Occupation-by-industry effects account for stable differences in their baseline levels. The design still cannot remove shocks specific to an occupation that happen to correlate with exposure.

## Data and measures

The unit is a detailed occupation by industry by “May” reference year. I will use publicly available OEWS national industry-specific estimates, occupational exposure data from Eloundou et al. (2024), and a fixed pre-2023 O\*NET version for occupational preparation measures. The main window will begin with 2021, when OEWS introduced its current model-based estimation method, and end with the latest available release at the time of analysis. This leaves 2021–2022 as the pre-period and 2023 onward as the post-period. I will verify consistent occupation and industry codes, restrict the main sample to comparable cells, and report the sample remaining after missing or suppressed estimates are removed. Earlier years, if used, will be descriptive context only.

Exposure is the occupation-level share of tasks estimated to be affected directly or with complementary software in Eloundou et al. (2024); I will standardize it across occupations so one unit equals one standard deviation. The two primary outcomes are the natural logarithms of OEWS total employment and mean annual wage. A positive coefficient on log wages indicates higher relative wage growth, not necessarily more workers. The post indicator equals one for 2023 and later. A financial and investment analyst is SOC 13-2051; bookkeeping, accounting, and auditing clerks are SOC 43-3031. These occupations illustrate analytical and more routine finance-related work, but they differ in education and other ways, so their comparison is descriptive.

## Model and hypotheses

The primary specification is: log(Yₒᵢₜ) = αₒᵢ + δᵢₜ + β(Exposureₒ × Postₜ) + εₒᵢₜ

Here, Y is employment or mean annual wage for occupation o in industry i and year t. α is an occupation-by-industry fixed effect; δ is an industry-by-year fixed effect. β estimates the average difference in post-2022 change associated with a one-standard-deviation difference in exposure, comparing occupations within the same industry and year. I will cluster standard errors by occupation because exposure does not vary across industries for an occupation. I will report coefficients, confidence intervals, sample sizes, and the corresponding approximate percentage differences.

H1 predicts β \< 0 for employment if exposed tasks are associated with displacement. The wage coefficient is a separate, two-sided outcome because productivity gains and reduced demand can push wages in different directions. A zero or positive employment estimate does not prove augmentation; it means this design has not detected the predicted displacement pattern. The small number of pre-period years also limits a strong parallel-trends assessment.

For the finance-focused analysis, I will plot annual employment and wage estimates for SOC 13-2051 and 43-3031 and estimate an analyst-by-post interaction where comparable industry cells exist. I will describe the analyst-minus-clerk difference as a contrast, not as a clean causal effect of GenAI: education, tasks, accounting software, and industry mix may differ. This keeps the financial analyst question central without treating one comparison occupation as a definitive counterfactual.

## Analysis and credibility checks

First, I will document data coverage by year, occupation, and industry and plot the exposure distribution. I will show unadjusted employment and wage trends for analysts and clerks. Second, I will estimate the primary fixed-effect model separately for employment and wages. Third, I will display annual exposure-by-year coefficients with 2022 as the reference to show the timing and direction of divergence. With only 2021 as another pre-year under the consistent-method window, this plot is a limited diagnostic, not a decisive test of parallel trends.

I will then repeat the same two primary models with 2024 onward coded as post, since OEWS combines six survey panels collected over three years and an immediate 2023 change could be muted. I will also estimate the models on cells observed in every included year and compare them with national occupation-level results to assess sensitivity to suppressed industry cells. Each check changes one feature of the primary comparison while retaining the same outcome and exposure definition. I will report all estimates, including null and opposite-signed findings, without treating a nonsignificant result as evidence that GenAI had no effect.

## Limitations and contribution

The main threats are occupation-specific trends correlated with exposure and the fact that task exposure is not observed in employer adoption. OEWS estimates are designed primarily for cross-sectional description; BLS explicitly cautions against using them as a time series because of pooled panels, changing classifications, and methodology (U.S. Bureau of Labor Statistics, n.d.). Restricting the main window to the current method and checking balanced cells improves comparability but does not solve that limitation. Thus, the project can identify suggestive differences in observed outcomes, not isolate GenAI as their cause.

The project will contribute a reproducible assessment of whether a prominent exposure measure aligns with subsequent official U.S. labor estimates, with a specific view of financial analysts. It will clarify what the data can and cannot say about changes in analyst demand and pay, giving later research a basis for designs that observe adoption or task changes more directly.

## Work plan

Weeks 1–2: download and audit OEWS and exposure data; record definitions, code changes, and suppression. Weeks 3–4: construct a documented occupation-industry panel, verify the exposure merge, and produce descriptive tables and plots. Weeks 5–8: estimate employment and wage models, the finance contrast, and specified sensitivity checks. Weeks 9–12: write results and limitations, share reproducible code, and prepare a working paper. Week 13: rerun the analysis from a clean environment and complete the submission.

## References

Acemoglu, D., & Restrepo, P. (2019). Automation and new tasks: How technology displaces and reinstates labor. Journal of Economic Perspectives, 33(2), 3–30. <https://www.aeaweb.org/articles?id=10.1257/jep.33.2.3>

Autor, D. H., Levy, F., & Murnane, R. J. (2003). The skill content of recent technological change: An empirical exploration. Quarterly Journal of Economics, 118(4), 1279–1333. <https://economics.mit.edu/sites/default/files/publications/the%20skill%20content%202003.pdf>

Eloundou, T., Manning, S., Mishkin, P., & Rock, D. (2024). GPTs are GPTs: Labor market impact potential of LLMs. Science, 384(6702), 1306–1308. <https://pubmed.ncbi.nlm.nih.gov/38900883/>

National Center for O\*NET Development. (n.d.). O\*NET database. <https://www.onetcenter.org/database.html>

Noy, S., & Zhang, W. (2023). Experimental evidence on the productivity effects of generative artificial intelligence. Science, 381(6654), 187–192. <https://pubmed.ncbi.nlm.nih.gov/37440646/>

U.S. Bureau of Labor Statistics. (n.d.). Occupational Employment and Wage Statistics: Frequently asked questions. <https://www.bls.gov/oes/oes_ques.html>
