// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';

interface TemplateStepperProps {
  steps: string[];
  current: number;
}

const TemplateStepper: React.FC<TemplateStepperProps> = ({ steps, current }) => (
  <div className="flex items-center gap-2 pb-1">
    {steps.map((label, index) => {
      const stepNumber = index + 1;
      const reached = current >= stepNumber;
      return (
        <React.Fragment key={label}>
          {index > 0 ? <div className="h-px w-8 bg-neutral-300" /> : null}
          <div className="flex items-center gap-2">
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                reached ? 'bg-brand-primary text-white' : 'bg-neutral-200 text-neutral-600'
              }`}>
              {stepNumber}
            </span>
            <span
              className={`text-sm ${
                current === stepNumber ? 'font-semibold' : 'text-neutral-500'
              }`}>
              {label}
            </span>
          </div>
        </React.Fragment>
      );
    })}
  </div>
);

export default TemplateStepper;
