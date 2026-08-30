import { Card, CardContent, CardHeader, Skeleton } from "@fintrace/ui";

export default function Loading() {
  return (
    <div className="space-y-6" aria-label="Loading FinTrace workspace" role="status">
      <div className="space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Card key={index}>
            <CardHeader className="space-y-3">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-8 w-20" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="space-y-3 p-5">
          {Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-10 w-full" />)}
        </CardContent>
      </Card>
    </div>
  );
}
