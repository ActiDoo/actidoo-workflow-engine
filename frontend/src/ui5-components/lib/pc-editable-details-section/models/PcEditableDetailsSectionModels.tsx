export enum PcDetailsSectionItemType {
  INPUT = 1,
  TEXTAREA,
  CHECKBOX,
  MULTI_INPUT,
  SELECT,
  STEP_INPUT,
}
export enum PcDetailsSectionTransformType {
  DATE = 1,
}

export interface PcDetailsSectionItem {
  label: string;
  key: string;
  description?: string;
  type?: PcDetailsSectionItemType;
  options?: PcDetailsItemOption[];
  transform?: PcDetailsSectionTransformType;
  required?: boolean;
  readonly?: boolean;
  visible?: boolean;
}
export interface PcDetailsItemOption {
  value: any;
  label: string;
}

interface PcDetailsSectionProps<T> {
  sections: PcDetailsSectionItem[][][];
  data?: T;
  loading?: boolean;
  isEditable?: boolean;
  onDelete?: () => void;
  onSave?: (obj: T | undefined) => void;
  saveLabel?: string;
  response?: number;
  deleteResponse?: number;
  saveResponse?: number;
  showError?: boolean;
  errorMessage?: string;
}
