import { Controller } from "react-hook-form";
import type { FieldErrors } from "react-hook-form";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export interface FormOption {
  value: string;
  label: string;
}

// Reusable RHF-bound select. `control` is loosely typed so any form can use it.
export function FormSelect({
  control,
  name,
  label,
  placeholder,
  options,
  errors,
  required,
  disabled,
}: {
  // Loosely typed so any RHF form can reuse this field.
  control: any;
  name: string;
  label: string;
  placeholder: string;
  options: FormOption[];
  errors: FieldErrors;
  required?: boolean;
  disabled?: boolean;
}) {
  const err = errors[name]?.message as string | undefined;
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="text-destructive"> *</span>}
      </Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <Select value={(field.value as string) || ""} onValueChange={field.onChange} disabled={disabled}>
            <SelectTrigger>
              <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
      {err && <p className="text-xs text-destructive">{err}</p>}
    </div>
  );
}
