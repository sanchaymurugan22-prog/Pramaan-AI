import { Fragment } from 'react'
import { Icon } from './Icon'

// The steps of a new transformation, as in the design "10 · New transformation · 2 Safety check":
// done steps get a green tick, the current one a saffron dot, later ones a grey number.
const STEPS = ['Add sources', 'Safety check', 'Outputs & settings', 'Generate']

export function Stepper({ current }: { current: number }) {
  return (
    <section className="card stepper" aria-label={`Step ${current} of ${STEPS.length}: ${STEPS[current - 1]}`}>
      {STEPS.map((label, index) => {
        const number = index + 1
        const state = number < current ? 'done' : number === current ? 'current' : 'todo'
        return (
          <Fragment key={label}>
            {index > 0 && <span className={number <= current ? 'step-line is-done' : 'step-line'} />}
            <span className={`step step-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
              <span className="step-dot">{state === 'done' ? <Icon name="check" size={16} strokeWidth={2.6} /> : number}</span>
              <span className="step-label">
                {label}
                {state === 'done' && <span className="sr-only"> (done)</span>}
              </span>
            </span>
          </Fragment>
        )
      })}
    </section>
  )
}
