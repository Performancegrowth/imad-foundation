import { forwardRef } from 'react'
import { cn } from '../../lib/utils.js'

// shadcn/ui Button (vendored) — same variants/sizes API, IMAD green/gold theme.
const VARIANTS = {
  default: 'im-btn-default',
  primary: 'im-btn-default',
  secondary: 'im-btn-secondary',
  outline: 'im-btn-outline',
  ghost: 'im-btn-ghost',
  destructive: 'im-btn-destructive',
  link: 'im-btn-link',
}
const SIZES = {
  default: 'im-btn-md',
  sm: 'im-btn-sm',
  small: 'im-btn-sm',
  lg: 'im-btn-lg',
  icon: 'im-btn-icon',
}

const Button = forwardRef(function Button(
  { variant = 'default', size = 'default', className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn('im-btn', VARIANTS[variant] || VARIANTS.default, SIZES[size] || SIZES.default, className)}
      {...props}
    />
  )
})

export { Button }
export default Button
