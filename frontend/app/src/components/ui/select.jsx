import { forwardRef } from 'react'
import { cn } from '../../lib/utils.js'

// shadcn/ui Select — native <select> styled to the IMAD theme (vendored).
// Same ergonomics as shadcn Select for our views: value/onChange/options.
const Select = forwardRef(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn('im-input', 'im-select', className)} {...props}>
      {children}
    </select>
  )
})

export { Select }
export default Select
