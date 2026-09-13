import { cn } from '../../lib/utils.js'

// shadcn/ui Card (vendored) — thin wrapper so views read like shadcn code
// while reusing the IMAD `.card` surface styles.
export function Card({ className, ...props }) {
  return <section className={cn('card', 'im-card', className)} {...props} />
}
export function CardHeader({ className, ...props }) {
  return <div className={cn('card-header', className)} {...props} />
}
export function CardTitle({ className, ...props }) {
  return <h3 className={cn('im-card-title', className)} {...props} />
}
export function CardDescription({ className, ...props }) {
  return <p className={cn('muted', 'im-card-desc', className)} {...props} />
}
export function CardContent({ className, ...props }) {
  return <div className={cn('im-card-content', className)} {...props} />
}
export function CardFooter({ className, ...props }) {
  return <div className={cn('im-card-footer', className)} {...props} />
}
export default Card
