/** Interpretation only: no model values, feature mappings or calculations change. */
export default function ModelExplanation({ kind }) {
  return <details className="dash-card" aria-label="Model estimate explanation">
    <summary><strong>How to read this estimate</strong></summary>
    {kind === 'salary' ? <>
      <p>This is an annual salary estimate in lakhs of rupees (LPA), conditional on getting placed. It is not an offer, a minimum salary or a guaranteed outcome.</p>
      <p>The salary model was trained on placed-student records. The existing service bounds inputs to its observed training range; different out-of-range inputs may produce similar estimates. Some activity counts are approximate representations of training features.</p>
      <p>Employer, role, location and current market conditions can change actual offers. No independently validated accuracy or confidence interval is supplied for this individual estimate.</p>
    </> : <>
      <p>This is the classifier's probability for the placed class using the submitted inputs. It is a model estimate, not a promise of placement or a measured student outcome.</p>
      <p>Model class confidence is the larger of the placed and not-placed probabilities. It comes from the same calculation; it is not model accuracy or independent evidence that the prediction is correct.</p>
      <p>Results depend on input quality and the model's training data. Readiness is a separate preparation score based on profile evidence. No independently validated real-world success rate is claimed here.</p>
    </>}
  </details>;
}
