import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useResourceList } from "./api";
import type { FieldDef } from "./config";

/** A master-backed <select> for the admin form. Each instance fetches its own
 * option list (so React hook rules hold even with a dynamic number of fields). */
export function ResourceSelectField({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: unknown;
  onChange: (v: string) => void;
}) {
  const list = useResourceList(field.optionsEndpoint!, true); // active options only
  return (
    <Select value={value ? String(value) : ""} onValueChange={onChange}>
      <SelectTrigger>
        <SelectValue placeholder={field.placeholder ?? `Select ${field.label.toLowerCase()}`} />
      </SelectTrigger>
      <SelectContent>
        {(list.data ?? []).map((row) => (
          <SelectItem key={String(row[field.optionValue!])} value={String(row[field.optionValue!])}>
            {String(row[field.optionLabel!] ?? row[field.optionValue!])}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
