// shadcn/ui + Tremor bridge — one import surface for vendored primitives.
// Components live in ./ui/* (Button, Input, Select, Card, Badge, Dialog,
// Tabs, Table, DropdownMenu) and charts live in ./charts.jsx, ./charts2.jsx,
// ./charts3.jsx. Views import from here so call sites read like real
// shadcn/ui + @tremor/react code.
export { Button } from './ui/button.jsx'
export { Input, Textarea, Label } from './ui/input.jsx'
export { Select } from './ui/select.jsx'
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './ui/card.jsx'
export { Badge } from './ui/badge.jsx'
export {
  Dialog, DialogHeader, DialogTitle, DialogDescription, DialogContent, DialogFooter,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
  DropdownMenu, useDialogState,
} from './ui/dialog.jsx'
export { ChartShell, AxisLabels, PALETTE, niceCeil } from './charts.jsx'
export { BarChart, LineChart, AreaChart } from './charts2.jsx'
export { DonutChart, ScatterChart, ProgressBar, Metric } from './charts3.jsx'
