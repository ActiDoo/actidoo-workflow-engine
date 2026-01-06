// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'brand-primary': 'var(--color-brand-primary, #007C84)',
        'brand-primary-strong': 'var(--color-brand-primary-strong, #006066)',
        'brand-primary-soft': 'var(--color-brand-primary-soft, #5bbac1)',
        'accent-positive': 'var(--color-accent-positive, #09AE3B)',
        'accent-positive-weak': 'var(--color-accent-positive-weak, #96BE0D)',
        'accent-warning': 'var(--color-accent-warning, #FFA800)',
        'accent-warning-soft': 'var(--color-accent-warning-soft, #FFE766)',
        'accent-negative': 'var(--color-accent-negative, #E00A18)',
        'accent-critical': 'var(--color-accent-critical, #D8124F)',
        'accent-highlight': 'var(--color-accent-highlight, #A3009B)',
        'neutral-0': 'var(--color-neutral-0, #FFFFFF)',
        'neutral-50': 'var(--color-neutral-50, #F4F4F4)',
        'neutral-100': 'var(--color-neutral-100, #E9E9E9)',
        'neutral-200': 'var(--color-neutral-200, #D2D2D2)',
        'neutral-400': 'var(--color-neutral-400, #A6A6A6)',
        'neutral-700': 'var(--color-neutral-700, #666A6E)',
        'neutral-800': 'var(--color-neutral-800, #505156)',
        'neutral-900': 'var(--color-neutral-900, #202020)',
        'surface-base': 'var(--color-surface-base, #F4F4F4)',
        'surface-contrast': 'var(--color-surface-contrast, #202020)',
        'border-subtle': 'var(--color-border-subtle, #D2D2D2)',
        'border-strong': 'var(--color-border-strong, #666A6E)',
        'text-default': 'var(--color-text-default, #202020)',
        'text-subtle': 'var(--color-text-subtle, #666A6E)',
      },
    },
    screens: {
      sm: '600px',
      md: '768px',
      lg: '1024px',
      xl: '1440px',
      '2xl': '1536px',
    },
  },
  plugins: [],
};
