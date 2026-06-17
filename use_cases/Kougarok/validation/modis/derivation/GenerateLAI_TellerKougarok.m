clear;clc;
% sitenm='Teller';id=1; inv=8;
sitenm='Kougarok';id=2;inv=4;

[tmpdata_all,txt,raw] = xlsread(['./TellerKougarokLAI/TellerKougarokLAI-MCD15A3H-061-results.xlsx']);

% field_id=10;%GPP field, kgC/m^2/8day, MYD17A2HGF_061_Gpp_500m
% factor=1000/8.0; %convert to C/m^2/day

field_id=11;%MCD15A3H_061_Lai_500m
factor=1;
tmpdata=tmpdata_all(tmpdata_all(:,1)==id,:);
tmpdata(tmpdata(:,field_id)>100,field_id)=NaN;

yearlis=2002:2023;
n=1;m=1;
for iyear=yearlis
    for imon=1:12
             
        for iday=1:eomday(iyear,imon)
            
                LAI_daily(n,1)=iyear;
                LAI_daily(n,2)=imon;
                LAI_daily(n,3)=iday;
                
                id=find(tmpdata(:,4)==iyear&tmpdata(:,5)==imon&tmpdata(:,6)==iday)
                if ~isempty(id)
                LAI_daily(n,4)=tmpdata(id,field_id);
                else
                LAI_daily(n,4)=NaN;   
                end
                
                n=n+1;
        end
        
    end
end
LAI_daily(:,4)=LAI_daily(:,4)*factor;
data_daily=[];
for iyear=yearlis
    data_tmp=LAI_daily(LAI_daily(:,1)==iyear,:);
for kk=1:inv:size(data_tmp,1) %8-day or 4-day product
    data_tmp((kk+1):min(kk+(inv-1),size(data_tmp,1)),4)=data_tmp(kk,4);
end
    data_daily=[data_daily',data_tmp']';
end

LAI_daily=data_daily;
LAI_monthly=monthlyavg(LAI_daily,LAI_daily(:,1:3),yearlis,10);

save([sitenm,'_MODISLAI_2002to2023.mat'],'LAI_daily','LAI_monthly');

plot(LAI_monthly(:,end),'LineWidth',3);
set(gca,'xtick',1:24*2:264,'xticklabel',LAI_monthly(1:24*2:264,1))
set(gca,'FontWeight','bold','FontSize',22,'LineWidth',1.5);
ylabel('MODIS LAI','FontWeight','bold','FontSize',22);


