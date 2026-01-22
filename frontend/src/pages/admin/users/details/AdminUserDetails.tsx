// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useMemo, useState } from 'react';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  DateTimePicker,
  Label,
  Text,
} from '@ui5/webcomponents-react';
import moment from 'moment';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import { PcPage } from '@/ui5-components';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import { State } from '@/store';
import { useSelectUiLoading } from '@/store/ui/selectors';
import {
  AdminUser,
  AdminUserDelegation,
  GetUserDetailResponse,
  UserDelegation,
} from '@/models/models';
import WeUserAutocomplete from '@/utils/components/WeUserAutocomplete';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { handleResponse } from '@/services/HelperService';
import { useTranslation } from '@/i18n';

const DATE_TIME_PATTERN = 'yyyy-MM-dd HH:mm';
const DISPLAY_DATE_TIME_PATTERN = 'YYYY-MM-DD HH:mm';

const toPickerValue = (iso?: string | null): string => {
  if (!iso) return '';
  const parsed = moment(iso);
  if (!parsed.isValid()) return '';
  return parsed.local().format(DISPLAY_DATE_TIME_PATTERN);
};

const toIsoDateTimeValue = (value?: string): string | null => {
  if (!value) return null;
  const parsed = moment(value, DISPLAY_DATE_TIME_PATTERN, true);
  if (!parsed.isValid()) return null;
  return parsed.toISOString();
};

const formatReadableDate = (iso?: string | null): string => {
  if (!iso) return '-';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
};

const mapDelegationsFromResponse = (
  delegations?: AdminUserDelegation[]
): UserDelegation[] => {
  if (!delegations) return [];
  return delegations
    .map(entry => {
      const id = entry.delegate?.id;
      if (!id) return null;
      const fullName =
        entry.delegate?.full_name ??
        entry.delegate?.username ??
        entry.delegate?.email ??
        id;
      return {
        delegate_user_id: id,
        valid_until: entry.valid_until ?? null,
        delegate: {
          id,
          full_name: fullName,
          email: entry.delegate?.email ?? undefined,
        },
      };
    })
    .filter(Boolean) as UserDelegation[];
};

const AdminUserDetails: React.FC = () => {
  const { t } = useTranslation();
  const { userId } = useParams();
  const dispatch = useDispatch();

  const detailState = useSelector((state: State) => state.data[WeDataKey.ADMIN_USER_DETAIL]);
  const delegationsState = useSelector(
    (state: State) => state.data[WeDataKey.ADMIN_SET_USER_DELEGATIONS]
  );
  const loadingDetail = useSelectUiLoading(WeDataKey.ADMIN_USER_DETAIL, 'POST');
  const savingDelegations = useSelectUiLoading(WeDataKey.ADMIN_SET_USER_DELEGATIONS, 'POST');

  const [userDetail, setUserDetail] = useState<GetUserDetailResponse | undefined>(undefined);
  const [delegations, setDelegations] = useState<UserDelegation[]>([]);
  const [pendingDelegate, setPendingDelegate] = useState<{ id?: string; label?: string }>({});
  const [pendingValidUntil, setPendingValidUntil] = useState<string>('');

  const targetUserId = userDetail?.user?.id ?? userId;

  useEffect(() => {
    if (userId) {
      dispatch(postRequest(WeDataKey.ADMIN_USER_DETAIL, { user_id: userId }));
    }
  }, [userId]);

  const syncDetailState = (detail?: GetUserDetailResponse | null) => {
    if (!detail) return;
    setUserDetail(detail);
    setDelegations(mapDelegationsFromResponse(detail.delegations));
  };

  useEffect(() => {
    syncDetailState(detailState?.data);
  }, [detailState?.data]);

  useEffect(() => {
    if (delegationsState?.data) {
      syncDetailState(delegationsState.data);
    }
  }, [delegationsState?.data]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_SET_USER_DELEGATIONS,
      delegationsState?.postResponse,
      t('adminUserDetails.saveSuccess'),
      t('adminUserDetails.saveError'),
      () => {
        if (!delegationsState?.data && targetUserId) {
          dispatch(postRequest(WeDataKey.ADMIN_USER_DETAIL, { user_id: targetUserId }));
        }
      }
    );
  }, [delegationsState?.postResponse]);

  const isDuplicatePendingDelegate = useMemo(() => {
    return pendingDelegate.id
      ? delegations.some(entry => entry.delegate_user_id === pendingDelegate.id)
      : false;
  }, [pendingDelegate.id, delegations]);

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
  };

  const handleSaveDelegations = () => {
    if (!targetUserId) return;
    const payload = {
      user_id: targetUserId,
      delegations: delegations.map(entry => ({
        delegate_user_id: entry.delegate_user_id,
        valid_until: entry.valid_until ?? null,
      })),
    };
    dispatch(postRequest(WeDataKey.ADMIN_SET_USER_DELEGATIONS, payload));
  };

  const renderUserInfo = (user?: AdminUser) => {
    if (!user) return null;
    return (
      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div className="flex flex-wrap justify-between gap-2">
          <div className="space-y-1">
            <Label className="font-semibold block text-lg">{t('adminUserDetails.account')}</Label>
            <Text className="text-sm text-neutral-700">
              {t('adminUserDetails.userId')}: {user.id}
            </Text>
          </div>
        </div>
        <WeDetailsTable
          data={[
            { label: t('adminUserDetails.username'), content: user.username },
            { label: t('adminUserDetails.email'), content: user.email },
            { label: t('adminUserDetails.firstName'), content: user.first_name },
            { label: t('adminUserDetails.lastName'), content: user.last_name },
            { label: t('adminUserDetails.fullName'), content: user.full_name },
            {
              label: t('adminUserDetails.serviceUser'),
              content: user.is_service_user ? t('common.labels.yes') : t('common.labels.no'),
            },
            { label: t('adminUserDetails.createdAt'), content: formatReadableDate(user.created_at) },
            {
              label: t('adminUserDetails.roles'),
              content: user.roles?.length ? user.roles.join(', ') : '-',
            },
          ]}
        />
      </div>
    );
  };

  const renderDelegations = () => {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div>
            <Label className="font-semibold block">{t('adminUserDetails.delegationsTitle')}</Label>
            <Text className="text-sm text-neutral-700">{t('adminUserDetails.delegationsHint')}</Text>
          </div>
          <Button
            design={ButtonDesign.Emphasized}
            disabled={savingDelegations || delegations.length === 0}
            onClick={handleSaveDelegations}>
            {t('adminUserDetails.saveDelegations')}
          </Button>
        </div>

        <div className="space-y-4">
          {delegations.length === 0 ? (
            <Text className="text-sm text-neutral-500">{t('adminUserDetails.noDelegations')}</Text>
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
                  <Text className="text-xs text-neutral-500">
                    {formatReadableDate(entry.valid_until)}
                  </Text>
                </div>
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="flex flex-col gap-1">
                    <Label>{t('adminUserDetails.validUntil')}</Label>
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
                    onClick={() => handleDelegationDateChange(entry.delegate_user_id, null)}>
                    {t('adminUserDetails.clearDeadline')}
                  </Button>
                  <Button
                    design={ButtonDesign.Negative}
                    icon="decline"
                    onClick={() => handleRemoveDelegation(entry.delegate_user_id)}>
                    {t('adminUserDetails.remove')}
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="border-t border-neutral-200 pt-4 space-y-3">
          <Label className="font-semibold block">{t('adminUserDetails.addDelegate')}</Label>
          <WeUserAutocomplete
            excludeUserIds={targetUserId ? [targetUserId] : undefined}
            onSelectUser={(selectedUserId, label) => {
              setPendingDelegate({ id: selectedUserId, label });
            }}
          />
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex flex-col gap-1">
              <Label>{t('adminUserDetails.validUntil')}</Label>
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
              design={ButtonDesign.Emphasized}
              disabled={!pendingDelegate.id || isDuplicatePendingDelegate}
              onClick={handleAddDelegation}>
              {t('adminUserDetails.addDelegate')}
            </Button>
          </div>
        </div>
      </div>
    );
  };

  const pageTitle =
    userDetail?.user?.full_name ||
    userDetail?.user?.username ||
    userDetail?.user?.email ||
    t('adminUserDetails.pageTitleFallback');

  const isLoading = loadingDetail && !userDetail;

  return (
    <PcPage header={{ title: t('adminUserDetails.pageTitle', { name: pageTitle }), showBack: true }}>
      {isLoading ? (
        <div className="flex justify-center py-12">
          <BusyIndicator active size="Large" />
        </div>
      ) : (
        <div className="space-y-6">
          {renderUserInfo(userDetail?.user as AdminUser | undefined)}
          {renderDelegations()}
          {savingDelegations && (
            <div className="flex justify-center">
              <BusyIndicator active size="Small" />
            </div>
          )}
        </div>
      )}
    </PcPage>
  );
};

export default AdminUserDetails;
