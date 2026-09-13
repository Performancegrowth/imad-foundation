import { forwardRef } from 'react'
import { cn } from '../../lib/utils.js'

// shadcn/ui Input (vendored).
const Input = forwardRef(function Input({ className, type = 'text', ...props }, ref) {
  return <input ref={ref} type={type} className={cn('im-input', className)} {...props} />
})

// shadcn/ui Textarea (vendored).
const Textarea = forwardRef(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn('im-input', 'im-textarea', className)} {...props} />
})

// shadcn/ui Label (vendored).
function Label({ className, ...props }) {
  return <label className={cn('im-label', className)} {...props} />
}

export { Input, Textarea, Label }
export default Input
