import { useEffect } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { COUNTRIES, DEFAULT_COUNTRY } from "@/lib/geo";

/**
 * Reusable Country dropdown. Defaults to India and is disabled while only one
 * country is supported; add entries to COUNTRIES (lib/geo) to enable more.
 */
export function CountrySelect({
  value,
  onChange,
  id,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
  disabled?: boolean;
}) {
  const lockedToSingle = COUNTRIES.length === 1;

  // Ensure the form captures the default even though the field is disabled.
  useEffect(() => {
    if (!value) onChange(DEFAULT_COUNTRY);
  }, [value, onChange]);

  return (
    <Select value={value || DEFAULT_COUNTRY} onValueChange={onChange} disabled={disabled || lockedToSingle}>
      <SelectTrigger id={id}>
        <SelectValue placeholder="Select country" />
      </SelectTrigger>
      <SelectContent>
        {COUNTRIES.map((c) => (
          <SelectItem key={c} value={c}>
            {c}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
