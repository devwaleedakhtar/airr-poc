import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";

export type ProgressStep = "uploading" | "converting" | "extracting" | "complete";

interface Step {
  id: ProgressStep;
  label: string;
  description: string;
}

const steps: Step[] = [
  {
    id: "uploading",
    label: "Upload",
    description: "Analyzing workbook structure",
  },
  {
    id: "converting",
    label: "Convert",
    description: "Preparing sheet for extraction",
  },
  {
    id: "extracting",
    label: "Extract",
    description: "Extracting data with AI",
  },
];

interface ProgressIndicatorProps {
  currentStep: ProgressStep;
  className?: string;
}

export function ProgressIndicator({ currentStep, className }: ProgressIndicatorProps) {
  const getCurrentStepIndex = () => {
    if (currentStep === "complete") return steps.length;
    return steps.findIndex((s) => s.id === currentStep);
  };

  const currentIndex = getCurrentStepIndex();

  const getStepStatus = (stepIndex: number) => {
    if (stepIndex < currentIndex) return "complete";
    if (stepIndex === currentIndex) return "current";
    return "pending";
  };

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const status = getStepStatus(index);
          const isLast = index === steps.length - 1;

          return (
            <div key={step.id} className="flex items-center flex-1">
              {/* Step */}
              <div className="flex flex-col items-center">
                {/* Icon */}
                <div className="flex items-center justify-center">
                  {status === "complete" && (
                    <CheckCircle2 className="h-8 w-8 text-green-600" />
                  )}
                  {status === "current" && (
                    <div className="relative">
                      <Circle className="h-8 w-8 text-primary" />
                      <Loader2 className="h-5 w-5 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-spin" />
                    </div>
                  )}
                  {status === "pending" && (
                    <Circle className="h-8 w-8 text-muted-foreground" />
                  )}
                </div>

                {/* Label */}
                <div className="mt-2 text-center">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      status === "complete" && "text-green-600",
                      status === "current" && "text-primary",
                      status === "pending" && "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </p>
                  {status === "current" && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {step.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Connector Line */}
              {!isLast && (
                <div className="flex-1 h-0.5 mx-4 mb-8">
                  <div
                    className={cn(
                      "h-full transition-colors",
                      status === "complete" ? "bg-green-600" : "bg-muted"
                    )}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
