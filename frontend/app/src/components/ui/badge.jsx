import { cn } from '../../lib/utils.js'

// shadcn/ui Badge (vendored).
const VARIANTS = {
  default: 'im-badge-default',
  secondary: '',
  success: 'success',
  ok: 'ok',
  warn: 'warn',
  fail: 'fail',
  outline: 'im-badge-outline',
  destructive: 'error-bad',
}
export function Badge({ variant = 'default', className, ...props }) {
  return <span className={cn('badge', 'pill', VARIANTS[variant] ?? '', className)} {...props} />
}
export default Badge
