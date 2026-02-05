// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useMemo, useState } from 'react';
import { useBlocker } from 'react-router-dom';

import { PcPage } from '@/ui5-components';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import {
  Select,
  Option,
  Label,
  Button,
  FlexBox,
  FlexBoxAlignItems,
  Text,
  DateTimePicker,
  ButtonDesign,
} from '@ui5/webcomponents-react';
import moment from 'moment';
import WeUserAutocomplete from '@/utils/components/WeUserAutocomplete';
import { UserDelegation } from '@/models/models';
import { handleResponse } from '@/services/HelperService';
import { useSelectUiLoading } from '@/store/ui/selectors';
import WeAlertDialog from '@/utils/components/WeAlertDialog';
import { useTranslation } from '@/i18n';

const DATE_TIME_PATTERN = 'yyyy-MM-dd HH:mm';
const DISPLAY_DATE_TIME_PATTERN = 'YYYY-MM-DD HH:mm';

const toPickerValue = (iso?: string | null): string => {
  if (!iso) return '';
  const parsed = moment(iso);
  if (!parsed.isValid()) return '';
  return parsed.local().format(DISPLAY_DATE_TIME_PATTERN);
};

const toIsoDateTimeValue = (value?: string | null): string | null => {
  if (!value) return null;
  const parsed = moment(value, DISPLAY_DATE_TIME_PATTERN, true);
  if (!parsed.isValid()) return null;
  return parsed.toISOString();
};

const formatReadableDate = (iso?: string | null, fallback?: string): string => {
  if (!iso) return fallback ?? 'No deadline';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return fallback ?? 'No deadline';
  return date.toLocaleString();
};

const cloneDelegations = (items: UserDelegation[] = []): UserDelegation[] =>
  items.map(entry => ({
    ...entry,
    delegate: entry.delegate ? { ...entry.delegate } : undefined,
  }));

const serializeDelegations = (items: UserDelegation[]): string =>
  JSON.stringify(
    cloneDelegations(items)
      .filter(entry => entry.delegate_user_id)
      .map(entry => ({
        delegate_user_id: entry.delegate_user_id,
        valid_until: entry.valid_until ?? null,
      }))
      .sort((a, b) => a.delegate_user_id.localeCompare(b.delegate_user_id))
  );

const UserSettings: React.FC = () => {
  const { t, changeLanguage, availableLanguages } = useTranslation();
  const key = WeDataKey.USER_SETTINGS;
  const dispatch = useDispatch();
  const data = useSelector((state: State) => state.data[key]);
  const currentUserId = useSelector(
    (state: State) => state.data[WeDataKey.WFE_USER]?.data?.id
  );
  const options = data?.data?.supported_locales?.length
    ? data.data.supported_locales
    : availableLanguages.map(lang => ({ key: lang.key, label: lang.label }));

  const [locale, setLocale] = useState<string>('');
  const [initialLocale, setInitialLocale] = useState<string>('');
  const [delegations, setDelegations] = useState<UserDelegation[]>([]);
  const [initialDelegations, setInitialDelegations] = useState<UserDelegation[]>([]);
  const [pendingDelegate, setPendingDelegate] = useState<{ id?: string; label?: string }>({});
  const [pendingValidUntil, setPendingValidUntil] = useState<string>('');
  const [showDelegateAddedNotice, setShowDelegateAddedNotice] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const saving = useSelectUiLoading(key, 'POST');

  const isDuplicatePendingDelegate = useMemo(() => {
    return pendingDelegate.id
      ? delegations.some(entry => entry.delegate_user_id === pendingDelegate.id)
      : false;
  }, [pendingDelegate.id, delegations]);

  const isDirty = useMemo(() => {
    return (
      locale !== initialLocale ||
      serializeDelegations(delegations) !== serializeDelegations(initialDelegations)
    );
  }, [delegations, initialDelegations, initialLocale, locale]);

  useEffect(() => {
    dispatch(getRequest(key));
  }, [dispatch, key]);

  useEffect(() => {
    if (!data?.data) return;

    const nextLocale = data.data.locale || '';
    const nextDelegations = cloneDelegations(data.data.delegations || []);

    setLocale(nextLocale);
    setInitialLocale(nextLocale);
    if (nextLocale) {
      changeLanguage(nextLocale);
    }
    setDelegations(nextDelegations);
    setInitialDelegations(nextDelegations);
  }, [data?.data, changeLanguage]);

  useEffect(() => {
    if (data?.postResponse === undefined) return;

    if (data.postResponse === 200) {
      const nextLocale = data.data?.locale ?? locale;
      const nextDelegations = cloneDelegations(data.data?.delegations ?? delegations);
      setLocale(nextLocale);
      setDelegations(nextDelegations);
      setInitialLocale(nextLocale);
      setInitialDelegations(nextDelegations);
    }

    handleResponse(
      dispatch,
      key,
      data?.postResponse,
      t('userSettings.saveSuccess') ?? 'Settings saved',
      t('userSettings.saveError') ?? 'Could not save settings. Please try again.'
    );
  }, [data?.postResponse, data?.data, dispatch, key, t]);

  const handleSave = () => {
    if (!isDirty || saving) return;

    changeLanguage(locale);
    const payload = {
      locale,
      delegations: delegations.map(entry => ({
        delegate_user_id: entry.delegate_user_id,
        valid_until: entry.valid_until ?? null,
      })),
    };
    dispatch(postRequest(key, payload));
    setShowDelegateAddedNotice(false);
  };

  const handleDelegationDateChange = (delegateId: string, isoValue?: string | null) => {
    setDelegations(prev =>
      prev.map(entry =>
        entry.delegate_user_id === delegateId
          ? { ...entry, valid_until: isoValue ?? null }
          : entry
      )
    );
  };

  const handleRemoveDelegation = (delegateId: string) => {
    setDelegations(prev => prev.filter(entry => entry.delegate_user_id !== delegateId));
    setShowDelegateAddedNotice(false);
  };

  const handleAddDelegation = () => {
    if (!pendingDelegate.id || isDuplicatePendingDelegate) {
      return;
    }
    setDelegations(prev => [
      ...prev,
      {
        delegate_user_id: pendingDelegate.id!,
        valid_until: pendingValidUntil || null,
        delegate: {
          id: pendingDelegate.id!,
          full_name: pendingDelegate.label ?? pendingDelegate.id!,
        },
      },
    ]);
    setPendingDelegate({});
    setPendingValidUntil('');
    setShowDelegateAddedNotice(true);
  };

  const blocker = useBlocker(isDirty);
  useEffect(() => {
    if (blocker.state === 'blocked') {
      setDialogOpen(true);
    }
  }, [blocker.state]);

  const renderUnsavedChangesDialog = (): React.ReactElement | null => {
    if (!dialogOpen) return null;
    return (
      <WeAlertDialog
        isDialogOpen={dialogOpen}
        setDialogOpen={setDialogOpen}
        title={t('common.unsavedChanges.title')}
        buttons={
          <>
            <Button
              design={ButtonDesign.Transparent}
              onClick={() => {
                blocker.reset?.();
                setDialogOpen(false);
              }}>
              {t('common.unsavedChanges.stay')}
            </Button>
            <Button
              design={ButtonDesign.Negative}
              onClick={() => {
                setDialogOpen(false);
                if (blocker.state === 'blocked') {
                  blocker.proceed();
                }
              }}>
              {t('common.unsavedChanges.leave')}
            </Button>
          </>
        }>
        <Text>{t('common.unsavedChanges.message')}</Text>
      </WeAlertDialog>
    );
  };

  return (
    <PcPage header={{ title: t('userSettings.title') }}>
      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4 mb-8">
        <Label className="font-semibold block mb-1">{t('userSettings.localeLabel')}</Label>
        <FlexBox className="items-center mb-4 flex-wrap gap-2" alignItems={FlexBoxAlignItems.Center}>
          <Select
            className="w-48"
            onChange={e => {
              const nextLocale = e.detail.selectedOption.getAttribute('data-key') || '';
              setLocale(nextLocale);
              changeLanguage(nextLocale);
            }}>
            {options.map(({ key, label }) => (
              <Option key={key} data-key={key} selected={key === locale}>
                {label}
              </Option>
            ))}
          </Select>
        </FlexBox>
        <div>
          <Text className="mr-2 text-sm text-neutral-700">
            {t('userSettings.localeHint')}
          </Text>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div>
          <Label className="font-semibold block mb-1">{t('userSettings.delegations.title')}</Label>
          <Text className="text-sm text-neutral-700">{t('userSettings.delegations.hint')}</Text>
        </div>

        <div className="space-y-4">
          {delegations.length === 0 ? (
            <Text className="text-sm text-neutral-500">
              {t('userSettings.delegations.empty')}
            </Text>
          ) : (
            delegations.map(entry => (
              <div
                key={entry.delegate_user_id}
                className="border border-neutral-200 rounded-lg p-4 flex flex-col gap-3 bg-neutral-50/40">
                <div className="flex flex-wrap justify-between gap-4">
                  <div>
                    <Text className="font-semibold block">
                      {entry.delegate?.full_name ?? entry.delegate_user_id}
                    </Text>
                    {entry.delegate?.email ? (
                      <Text className="text-sm text-neutral-600">
                        &nbsp;({entry.delegate.email})
                      </Text>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="flex flex-col gap-1">
                    <Label>{t('userSettings.delegations.validUntil')}</Label>
                    <DateTimePicker
                      className="w-64"
                      formatPattern={DATE_TIME_PATTERN}
                      value={toPickerValue(entry.valid_until)}
                      onChange={event =>
                        handleDelegationDateChange(
                          entry.delegate_user_id,
                          toIsoDateTimeValue(event.detail.value)
                        )
                      }
                    />
                  </div>
                  <Button
                    design={ButtonDesign.Transparent}
                    disabled={!entry.valid_until}
                    onClick={() => handleDelegationDateChange(entry.delegate_user_id, null)}>
                    {t('userSettings.delegations.clearDeadline')}
                  </Button>
                  <Button
                    design={ButtonDesign.Negative}
                    icon="decline"
                    onClick={() => handleRemoveDelegation(entry.delegate_user_id)}>
                    {t('userSettings.delegations.remove')}
                  </Button>
                </div>
              </div>
            ))
          )}

          {showDelegateAddedNotice && (
            <Text className="text-xs text-amber-700">
              {t('common.delegations.addedNotice')}
            </Text>
          )}
        </div>

        <div className="border-t border-neutral-200 pt-4 space-y-3">
          <Label className="font-semibold block">
            {t('userSettings.delegations.add')} {t('common.delegations.addHint')}
          </Label>
          <WeUserAutocomplete
            excludeUserIds={currentUserId ? [currentUserId] : undefined}
            onSelectUser={(userId, label) => {
              setPendingDelegate({ id: userId, label });
            }}
          />
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex flex-col gap-1">
              <Label>{t('userSettings.delegations.validUntil')}</Label>
              <DateTimePicker
                className="w-64"
                formatPattern={DATE_TIME_PATTERN}
                value={toPickerValue(pendingValidUntil)}
                onChange={event =>
                  setPendingValidUntil(toIsoDateTimeValue(event.detail.value) ?? '')
                }
              />
            </div>
            <Button
              design={ButtonDesign.Transparent}
              disabled={!pendingValidUntil}
              onClick={() => setPendingValidUntil('')}>
              {t('userSettings.delegations.clearDeadline')}
            </Button>
            <Button
              design={ButtonDesign.Emphasized}
              disabled={!pendingDelegate.id || isDuplicatePendingDelegate}
              onClick={handleAddDelegation}>
              {t('userSettings.delegations.add')}
            </Button>
            <Button
              design={ButtonDesign.Transparent}
              onClick={() => {
                setPendingDelegate({});
                setPendingValidUntil('');
              }}>
              {t('userSettings.delegations.resetSelection')}
            </Button>
          </div>
          {isDuplicatePendingDelegate ? (
            <Text className="text-xs text-red-500">
              {t('userSettings.delegations.duplicateWarning')}
            </Text>
          ) : null}
        </div>
      </div>

      <Button
        className="mt-6"
        design={ButtonDesign.Emphasized}
        disabled={!isDirty || !!saving}
        onClick={handleSave}>
        {t('userSettings.save')}
      </Button>

      {renderUnsavedChangesDialog()}
    </PcPage>
  );
};

export default UserSettings;
